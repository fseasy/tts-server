from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader

from .config import CONF

API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

MY_SECRET_KEY = CONF.auth_apikey


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
  if api_key != MY_SECRET_KEY:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Invalid API Key: {api_key}")
  return api_key
