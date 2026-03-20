from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from ..config.data_types import TtsBaseOption


class TtsProvider[TtsOptionT: TtsBaseOption](ABC):
  @abstractmethod
  async def synthesize(self, text: str, option: TtsOptionT | None = None) -> AsyncGenerator[bytes, None]:
    if False:
      yield b""

  @abstractmethod
  def sync_synthesize(self, text: str, option: TtsOptionT | None = None) -> bytes:
    import asyncio

    async def _get_all() -> bytes:
      chunks: list[bytes] = []
      async for d in self.synthesize(text=text, option=option):
        chunks.append(d)
      return b"".join(chunks)

    return asyncio.run(_get_all())

  @abstractmethod
  def sync_batch_synthesize(self, texts: list[str], option: TtsOptionT | None = None) -> list[bytes]:
    """Currently we only provide a sync way"""
    #! the default impl just use for loops without parallel (because concurrency might be limited)
    result_bytes: list[bytes] = []
    for t in texts:
      one_bytes = self.sync_synthesize(text=t, option=option)
      result_bytes.append(one_bytes)
    return result_bytes
