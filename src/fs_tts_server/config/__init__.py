import os

from fs_pyutils.log_builder import SyslogLogField, build_logger

from .constant import TTS_MODEL2QUALITY_VALUE
from .data_types import Env

__all__ = ["TTS_MODEL2QUALITY_VALUE"]

_env_str = os.getenv("env") or os.getenv("ENV")


if not _env_str:
  raise RuntimeError("No `ENV` variable is exported before running! set `ENV=dev` or `ENV=prod`!")
try:
  env = Env(_env_str)
except ValueError as e:
  raise RuntimeError(f"Invalid ENV value: {_env_str}, candidates={[v for v in Env]}") from e


if env == Env.DEV:
  from .dev import app_conf as _app_conf
else:
  from .prod import app_conf as _app_conf

CONF = _app_conf


_syslog_field = SyslogLogField(host=CONF.app_domain, tag="tts_fastapi")
LOGGER = build_logger(CONF.app_name, CONF.log_level, syslog_address=CONF.syslog_addr, syslog_log_field=_syslog_field)

LOGGER.info(f"Loaded client and server environmental vars for ENV={env}")
