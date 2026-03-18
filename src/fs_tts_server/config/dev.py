import logging

from .data_types import AppConf, EdgeTtsOption, Env, TtsBaseOption, TtsModel

_enabled_tts_provider2option: dict[TtsModel, TtsBaseOption] = {TtsModel.EDGE: EdgeTtsOption()}

app_conf = AppConf(
  env=Env.DEV,
  app_domain="http://127.0.0.1:3101",
  log_level=logging.DEBUG,
  auth_apikey="dev.fs-tts-server",
  cors_allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?",
  enabled_tts_provider2option=_enabled_tts_provider2option,
)
