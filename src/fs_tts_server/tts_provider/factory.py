from typing import Any
from ..config import CONF, LOGGER as logger
from ..config.data_types import TtsModel
from ..exceptions import LogicError
from .base import TtsProvider, TtsBaseOption


class TtsProviderFactory:
  _instances: dict[TtsModel, TtsProvider[Any]] = {}

  @classmethod
  def init(cls) -> None:

    for model, option in CONF.enabled_tts_provider2option.items():
      if model in cls._instances:
        continue
      logger.info(f"TTS provider: init {model}")

      provider: TtsProvider

      if model == TtsModel.EDGE:
        from .impl.edge import EdgeTtsOption, EdgeTtsProvider

        assert isinstance(option, EdgeTtsOption)
        provider = EdgeTtsProvider(option)
      else:
        raise LogicError(f"Unknown tts model: {model}")
      cls._instances[model] = provider

  @classmethod
  def get_provider(cls, model: TtsModel) -> TtsProvider | None:
    return cls._instances.get(model, None)
