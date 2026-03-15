from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from ..config.data_types import TtsBaseOption


class TtsProvider[TtsOptionT: TtsBaseOption](ABC):
  @abstractmethod
  async def synthesize(self, text: str, option: TtsOptionT | None = None) -> AsyncGenerator[bytes, None]:
    if False:
      yield b""
