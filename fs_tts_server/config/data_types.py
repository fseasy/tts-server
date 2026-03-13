import logging
from enum import StrEnum

from pydantic import BaseModel


class Env(StrEnum):
  DEV = "dev"
  PROD = "prod"


class AppConf(BaseModel):
  env: Env
  app_name: str = "tts-server"
  app_domain: str
  """Used for logger"""
  log_level: int = logging.INFO
  syslog_addr: tuple[str, int] = ("127.0.0.1", 11514)
  auth_apikey: str
