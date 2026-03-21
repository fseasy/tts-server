# see https://gunicorn.org/reference/settings/#config

import os

# --- Gunicorn 配置 ---
bind = "127.0.0.1:6001"
workers = 1
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 60
loglevel = "info"
logger_class = "fs_pyutils.gunicorn_logger.GunicornSyslogLogger"

# --- 核心“科学”逻辑 ---

# 1. 拦截 Systemd 的通知 Socket
# Gunicorn 内部逻辑是：如果检测到环境变量 NOTIFY_SOCKET，就会在启动后发送 READY=1。
# 我们在 Gunicorn 初始化前把它移走，存入自定义变量中。
_real_notify_socket = os.environ.pop("NOTIFY_SOCKET", None)
if _real_notify_socket:
  # 存入一个 Gunicorn 不认识，但我们代码能找到的变量名
  os.environ["CUSTOM_NOTIFY_SOCKET"] = _real_notify_socket


def on_starting(server):
  """
  Gunicorn Master 启动前的钩子
  此时 Gunicorn 发现环境变量里没有 NOTIFY_SOCKET，它就会变回 'simple' 模式的行为
  """
  server.log.info("Systemd NOTIFY_SOCKET intercepted. Manual notification enabled.")


# 你也可以在这里配置其他钩子，比如 worker 退出时的逻辑
