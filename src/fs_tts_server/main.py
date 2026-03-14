from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fs_tts_server.exceptions import ApiBaseException
from fs_tts_server.repositories import lifespan_db
from fs_tts_server.route_stat import RouteStatsMiddleware
from fs_tts_server.routes import admin_router, internal_auth_router, user_router
from starlette.middleware.cors import CORSMiddleware

from fs_tts_server import config

logger = config.LOGGER

logger.info("Init TTS server")


def _init_stripe() -> None:
  import stripe

  stripe.api_key = config.STRIPE_API_KEY


_init_stripe()


logger.info("Build app")


@asynccontextmanager
async def lifespan_main(app: FastAPI) -> AsyncGenerator[Any, None]:
  async with lifespan_db(app):
    await async_init_roles()
    yield


app = FastAPI(title=f"{config.APP_NAME}-backend", lifespan=lifespan_main)

app.add_middleware(get_middleware())  # type: ignore

# start apis. NOTE: we've added the same prefix for all our self-hosted api! (for nginx routing!)
app.include_router(admin_router, prefix=config.API_COMMON_BASE_PATH)
app.include_router(internal_auth_router, prefix=config.API_COMMON_BASE_PATH)
app.include_router(user_router, prefix=config.API_COMMON_BASE_PATH)
app.include_router(stripe_router, prefix=config.API_COMMON_BASE_PATH)


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
app.add_middleware(
  CORSMiddleware,
  allow_origins=[config.WEBSITE_DOMAIN],
  allow_credentials=True,
  allow_methods=["GET", "PUT", "POST", "DELETE", "OPTIONS", "PATCH"],
  allow_headers=["Content-Type"] + get_all_cors_headers(),
)
app.add_middleware(RouteStatsMiddleware)
