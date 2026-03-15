import logging

from .data_types import AppConf, EdgeTtsOption, Env, TtsBaseOption, TtsModel

_enabled_tts_provider2option: dict[TtsModel, TtsBaseOption] = {TtsModel.EDGE: EdgeTtsOption()}

app_conf = AppConf(
  env=Env.DEV,
  app_domain="http://localhost",
  log_level=logging.DEBUG,
  auth_apikey="dev.fs-tts-server",
  enabled_tts_provider2option=_enabled_tts_provider2option,
)
