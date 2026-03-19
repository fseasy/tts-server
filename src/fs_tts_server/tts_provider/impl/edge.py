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
