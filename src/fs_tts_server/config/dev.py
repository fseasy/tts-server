import logging

from .data_types import AppConf, EdgeTtsOption, Env, Qwen3TtsOption, Qwen3TtsRequestOption, TtsBaseOption, TtsModel

_enabled_tts_provider2option: dict[TtsModel, TtsBaseOption] = {
  TtsModel.EDGE: EdgeTtsOption(),
  TtsModel.QWEN3_TTS: Qwen3TtsOption(
    request_option=Qwen3TtsRequestOption(base_url="http://192.168.5.66:17651"), audio_fmt="wav"
  ),
}

app_conf = AppConf(
  env=Env.DEV,
  app_domain="http://127.0.0.1:6001",
  log_level=logging.DEBUG,
  auth_apikey="dev.fs-tts-server",
  cors_allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?",
  enabled_tts_provider2option=_enabled_tts_provider2option,
)
