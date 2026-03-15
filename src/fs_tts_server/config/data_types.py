import logging
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class Env(StrEnum):
  DEV = "dev"
  PROD = "prod"


# Define enums
class TtsModel(StrEnum):
  LIGHT_WEIGHT = "light_weight"
  """A semantic model name"""

  EDGE = "edge"  # edge-tts. Thank you.

  def actual_impl(self) -> "TtsModel":
    _m = {TtsModel.LIGHT_WEIGHT: TtsModel.EDGE}  #! currently, light-weight points to EDGE
    return _m.get(self, self)


class TtsBaseOption(BaseModel): ...


EdgeVoiceT = Literal[
  "en-US-AvaMultilingualNeural",  # Female Conversation, Copilot  Expressive, Caring, Pleasant, Friendly
  "en-US-EmmaMultilingualNeural",  # Female Conversation, Copilot  Cheerful, Clear, Conversational
  "en-US-JennyNeural",  # Female General Friendly, Considerate, Comfort
  "en-US-AnaNeural",  # Female Cartoon, Conversation, Cute
]


class EdgeTtsOption(TtsBaseOption):
  voice: EdgeVoiceT = "en-US-EmmaMultilingualNeural"  # this one sounds more friendly


class AppConf(BaseModel):
  env: Env
  app_name: str = "tts-server"
  app_domain: str
  """Used for logger"""
  log_level: int = logging.INFO
  syslog_addr: tuple[str, int] = ("127.0.0.1", 11514)
  auth_apikey: str
  enabled_tts_provider2option: dict[TtsModel, TtsBaseOption]
  """Note, here you just need to define the actual impl options that you want to enable"""
