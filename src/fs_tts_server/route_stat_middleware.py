import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import LOGGER as logger


class RouteStatsMiddleware(BaseHTTPMiddleware):
  async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    # --- 1. 请求开始计时 ---
    start_time = time.perf_counter()

    # --- 2. 执行后续的中间件和业务逻辑 ---
    # 如果 Supertokens 或业务代码报错，这里会抛出异常
    try:
      response = await call_next(request)
    except Exception as e:
      # 如果发生了未捕获的异常（比如 500），我们也想记录耗时
      # 这里记录后重新抛出，交给 FastAPI 的 ExceptionHandler 处理
      self._log_request(request, 500, start_time, error=e)
      raise e

    # --- 3. 请求正常结束，记录日志 ---
    self._log_request(request, response.status_code, start_time)

    return response

  def _log_request(self, request: Request, status_code: int, start_time: float, error: Exception | None = None) -> None:
    """
    统一的日志打印函数
    """
    # 计算耗时 (s)
    process_time = time.perf_counter() - start_time

    # 获取 IP (处理一些代理情况，防止报错)
    client_ip = request.client.host if request.client else "unknown"

    # 构造 Extra 字段 (会被 JsonSyslogFormatter 展平)
    _route = request.scope.get("route")
    uri = _route.path if _route else request.url.path
    log_payload = {
      "method": request.method,
      "path": uri,
      "status": status_code,
      "request_time": round(process_time, 2),  # align the name to the Nginx
      "ip": client_ip,
    }

    # 如果有异常信息，也可以加进去
    if error:
      log_payload["error_type"] = type(error).__name__

    logger.info(f"{request.method} {request.url.path}", extra=log_payload)
