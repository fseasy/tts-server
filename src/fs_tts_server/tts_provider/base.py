from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from ..config.data_types import TtsBaseOption


class TtsProvider[TtsOptionT: TtsBaseOption](ABC):
  @abstractmethod
  async def synthesize(self, text: str, option: TtsOptionT | None = None) -> AsyncGenerator[bytes, None]:
    if False:
      yield b""

  def sync_synthesize(self, text: str, option: TtsOptionT | None = None) -> bytes:
    import asyncio

    async def _get_all() -> bytes:
      chunks: list[bytes] = []
      async for d in self.synthesize(text=text, option=option):
        chunks.append(d)
      return b"".join(chunks)

    return asyncio.run(_get_all())
