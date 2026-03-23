import io
import json
import zipfile
from collections.abc import AsyncGenerator

import httpx
from pydantic import BaseModel

from fs_tts_server.config.data_types import Qwen3TtsAudioFmtT, Qwen3TtsOption

from ..base import TtsProvider


class TtsReq(BaseModel):
  speaker_name: str
  text: str
  language: str
  audio_fmt: Qwen3TtsAudioFmtT


class BatchTtsReq(BaseModel):
  speaker_name: str
  texts: list[str]
  languages: list[str]
  audio_fmt: Qwen3TtsAudioFmtT  # can only assign 1 fmt


class ManifestItem(BaseModel):
  text: str
  language: str
  audio_name: str


class Manifest(BaseModel):
  items: list[ManifestItem]


class Qwen3TtsProvider(TtsProvider[Qwen3TtsOption]):
  def __init__(self, option: Qwen3TtsOption):
    self._option = option
    self._async_client = httpx.AsyncClient()
    self._client = httpx.Client()

  async def synthesize(self, text: str, option: Qwen3TtsOption | None = None) -> AsyncGenerator[bytes, None]:
    if not option:
      option = self._option

    request = TtsReq(
      speaker_name=option.voice,
      text=text,
      language=option.language,
      audio_fmt=option.audio_fmt,
    )

    req_opt = option.request_option
    url = f"{req_opt.base_url}/tts"
    timeout = httpx.Timeout(connect=5, read=req_opt.timeout, write=5, pool=10)
    try:
      async with self._async_client.stream("POST", url, json=request.model_dump(), timeout=timeout) as resp:
        resp.raise_for_status()
        async for chunk in resp.aiter_bytes(chunk_size=8192):
          yield chunk
    except httpx.HTTPStatusError as e:
      raise RuntimeError(
        f"request `{url}` get bad http code: code={e.response.status_code}, text={e.response.text}"
      ) from e
    except Exception as e:
      raise RuntimeError(f"request `{url}` get exception: {e}") from e

  def sync_synthesize(self, text: str, option: Qwen3TtsOption | None = None) -> bytes:
    return super().sync_synthesize(text, option)

  def sync_batch_synthesize(self, texts: list[str], option: Qwen3TtsOption | None = None) -> list[bytes]:
    """We'll call the batch api"""
    if not option:
      option = self._option

    request = BatchTtsReq(
      speaker_name=option.voice,
      texts=texts,
      languages=[option.language] * len(texts),  # just set the same!
      audio_fmt=option.audio_fmt,
    )

    req_opt = option.request_option
    url = f"{req_opt.base_url}/batch-tts"
    timeout = httpx.Timeout(connect=5, read=req_opt.timeout, write=5, pool=10)
    try:
      resp = self._client.post(url, json=request.model_dump(), timeout=timeout)
      resp.raise_for_status()
    except httpx.HTTPStatusError as e:
      # let's include the full response.text to easily debug
      raise RuntimeError(
        f"request `{url}` get bad http code: code={e.response.status_code}, text={e.response.text}"
      ) from e
    except Exception as e:
      raise RuntimeError(f"request `{url}` get exception: {e}") from e

    # resp is a zip file, contains the audio datas as well as a manifest.json
    audio_bytes: list[bytes] = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
      manifest = Manifest.model_validate(json.loads(zf.read("manifest.json")))
      # it's ordered!
      for idx, item in enumerate(manifest.items):
        cur_text = item.text
        assert cur_text == texts[idx], f"Server returned text != input text, [{cur_text}] v.s. [{texts[idx]}]"
        audio_bytes.append(zf.read(item.audio_name))
    return audio_bytes
