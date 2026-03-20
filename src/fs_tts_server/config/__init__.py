import os

from fs_pyutils.log_builder import build_logger

from .data_types import Env, TtsModel

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
  from .dev import app_conf as _app_conf

CONF = _app_conf

TTS_MODEL2QUALITY_VALUE = {TtsModel.EDGE: 0, TtsModel.QWEN3_TTS: 5}

LOGGER = build_logger(
  CONF.app_name,
  CONF.log_level,
  syslog_address=CONF.syslog_addr,
  domain=CONF.app_domain,
)

LOGGER.info(f"Loaded client and server environmental vars for ENV={env}")
