from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fs_pyutils.systemd_notifier import systemd_notifier_lifespan

from fs_tts_server.config import CONF, LOGGER as logger
from fs_tts_server.exceptions import ApiBaseException
from fs_tts_server.repositories import lifespan_db
from fs_tts_server.route_stat_middleware import RouteStatsMiddleware
from fs_tts_server.routes_cached_tts import cached_tts_router

logger.info("Init TTS server")

# ! NOTE: currently we don't need to support a live tts api, so it's not required to init it.
# def _init_tts() -> None:
#   from fs_tts_server.tts_provider.factory import TtsProviderFactory
#   TtsProviderFactory.init()
#
# _init_tts()

logger.info("Build app")


@asynccontextmanager
async def lifespan_main(app: FastAPI) -> AsyncGenerator[Any, None]:
  async with lifespan_db(app) as async_engine:
    async with systemd_notifier_lifespan(app, async_db_engine=async_engine, logger=logger):
      logger.info("Server fully loaded.")
      yield


app = FastAPI(title=f"{CONF.app_name}-backend", lifespan=lifespan_main)

# CORS config, or it will get 405 in browser side (not affect the api request)
app.add_middleware(
  CORSMiddleware,
  allow_origin_regex=CONF.cors_allow_origin_regex,
  allow_credentials=True,
  allow_methods=["*"],  # 允许所有方法，包括 OPTIONS
  allow_headers=["*"],  # 允许所有头，包括 Content-Type
)

# start apis. NOTE: we've added the same prefix for all our self-hosted api! (for nginx routing!)
app.include_router(cached_tts_router)


@app.exception_handler(RequestValidationError)
async def input_param_validation_handler(exec: RequestValidationError) -> JSONResponse:
  return JSONResponse(content={"error_type": "invalid-input-param", "error_detail": str(exec)}, status_code=400)


@app.exception_handler(ApiBaseException)
async def internal_exception_handler(exec: ApiBaseException) -> JSONResponse:
  return JSONResponse(content={"error_type": "internal-error", "error_detail": str(exec)}, status_code=500)


@app.exception_handler(Exception)
async def unknown_internal_exception_handler(exec: Exception) -> JSONResponse:
  return JSONResponse(content={"error_type": "unknown-internal-error", "error_detail": str(exec)}, status_code=500)


# after all the apis
app.add_middleware(RouteStatsMiddleware)
