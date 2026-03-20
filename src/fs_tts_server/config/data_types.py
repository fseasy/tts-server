import logging
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Env(StrEnum):
  DEV = "dev"
  PROD = "prod"


# Define enums
class TtsModel(StrEnum):
  EDGE = "edge"  # edge-tts. Thank you.
  QWEN3_TTS = "qwen3-tts"  # thank you qwen3-tts


class TtsBaseOption(BaseModel): ...


EdgeVoiceT = Literal[
  "en-US-AvaMultilingualNeural",  # Female Conversation, Copilot  Expressive, Caring, Pleasant, Friendly
  "en-US-EmmaMultilingualNeural",  # Female Conversation, Copilot  Cheerful, Clear, Conversational
  "en-US-JennyNeural",  # Female General Friendly, Considerate, Comfort
  "en-US-AnaNeural",  # Female Cartoon, Conversation, Cute
]


class EdgeTtsOption(TtsBaseOption):
  voice: EdgeVoiceT = "en-US-EmmaMultilingualNeural"  # this one sounds more friendly


Qwen3TtsVoiceT = Literal["dajuan_english"]
Qwen3TtsAudioFmtT = Literal["mp3", "wav"]
Qwen3TtsLanguageT = Literal[
  "Chinese", "English", "Japanese", "Korean", "German", "French", "Russian", "Portuguese", "Spanish", "Italian"
]


class Qwen3TtsRequestOption(BaseModel):
  base_url: str = "http://localhost:17651"
  timeout: int = 120


class Qwen3TtsOption(TtsBaseOption):
  voice: Qwen3TtsVoiceT = "dajuan_english"
  audio_fmt: Qwen3TtsAudioFmtT = "mp3"
  language: Qwen3TtsLanguageT = "English"
  request_option: Qwen3TtsRequestOption = Field(default_factory=Qwen3TtsRequestOption)


def _default_syslog_addr() -> None | tuple[str, int]:
  import os

  # in format `ip:port`, like: "127.0.0.1:5140"
  syslog_addr_str = os.getenv("SYSLOG_ADDRESS", None)
  if not syslog_addr_str:
    return None
  try:
    ip, port = syslog_addr_str.split(":")
    return (ip, int(port))
  except Exception:
    return None


class AppConf(BaseModel):
  env: Env
  app_name: str = "tts-server"
  app_domain: str
  """Used for logger"""
  cors_allow_origin_regex: str
  r"""For CORS, an example: https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)? """
  log_level: int = logging.INFO
  syslog_addr: tuple[str, int] | None = Field(default_factory=_default_syslog_addr)
  auth_apikey: str
  enabled_tts_provider2option: dict[TtsModel, TtsBaseOption]
