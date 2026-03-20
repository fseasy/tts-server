from collections.abc import AsyncGenerator

from fs_tts_server.config.data_types import EdgeTtsOption

from ..base import TtsProvider


class EdgeTtsProvider(TtsProvider[EdgeTtsOption]):
  def __init__(self, option: EdgeTtsOption):
    self._option = option

  async def synthesize(self, text: str, option: EdgeTtsOption | None = None) -> AsyncGenerator[bytes, None]:
    import edge_tts

    if not option:
      option = self._option

    communicate = edge_tts.Communicate(text, option.voice)
    async for chunk in communicate.stream():
      if chunk["type"] == "audio" and "data" in chunk:
        yield chunk["data"]

  def sync_synthesize(self, text: str, option: EdgeTtsOption | None = None) -> bytes:
    return super().sync_synthesize(text, option)

  def sync_batch_synthesize(self, texts: list[str], option: EdgeTtsOption | None = None) -> list[bytes]:
    return super().sync_batch_synthesize(texts, option)
