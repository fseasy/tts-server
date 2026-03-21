import asyncio
import io
import json
from pathlib import Path

import httpx
from pydantic import BaseModel

from fs_tts_server.config import LOGGER as logger
from fs_tts_server.config.data_types import TtsModel
from fs_tts_server.repositories import TtsIdGenFnVersionT

_client = None
_client_loop = None


def get_async_client() -> httpx.AsyncClient:
  """Create global var for connection reuse;
  Create new async if event loop changes, or you'll get RuntimeError: Event loop is closed
  """
  global _client, _client_loop
  loop = asyncio.get_running_loop()

  if _client is None or _client_loop != loop:
    _client = httpx.AsyncClient(
      limits=httpx.Limits(max_connections=100),
      follow_redirects=True,
      transport=httpx.AsyncHTTPTransport(retries=3, http2=True),
    )
    _client_loop = loop

  return _client


class CachedTtsListData(BaseModel):
  text: str
  project: str
  tts_model: TtsModel
  is_valid_audio: bool


async def async_list(
  base_url: str, api_key: str, *, project: str, log_process: bool = False
) -> list[CachedTtsListData]:
  API = "/cached-tts/list"
  url = f"{base_url.rstrip('/')}{API}"
  headers = {"X-API-KEY": api_key}
  data = {"project": project}

  server_data: list[CachedTtsListData] = []
  timeout = httpx.Timeout(connect=5, read=120, write=10, pool=5)
  async with get_async_client().stream("POST", url, json=data, headers=headers, timeout=timeout) as response:
    try:
      response.raise_for_status()
    except httpx.HTTPStatusError as e:
      try:
        content = (await response.aread()).decode()
      except Exception as ex:
        content = f"none due to exception: {ex}"
      logger.critical(f"Request `/cache-tts/list` failed: Status code: {e.response.status_code} content: {content}")
      raise
    cnt = 0
    async for line in response.aiter_lines():
      cnt += 1
      if log_process and cnt % 100 == 0:
        logger.info(f"list get {cnt} lines")
      if not line:
        continue
      try:
        data = json.loads(line)
        is_valid = data["is_valid_audio"]
        d = CachedTtsListData(
          text=data["text"], project=project, tts_model=TtsModel(data["tts_model"]), is_valid_audio=is_valid
        )
      except Exception as e:
        logger.info(f"`/cached-tts/list` return invalid jsonl line: [{line}], err={e}")
        raise
      server_data.append(d)
  return server_data


async def async_add(
  base_url: str,
  api_key: str,
  *,
  text: str,
  project: str,
  tts_model: TtsModel,
  mp3_audio_data: bytes | io.BytesIO,
  id_version: TtsIdGenFnVersionT = "v1",
) -> None:
  """Add audio data"""
  url = f"{base_url.rstrip('/')}/cached-tts/add"
  headers = {"X-API-KEY": api_key}

  # 如果是 bytes，直接封装；如果是 BytesIO，确保指针在开头
  if isinstance(mp3_audio_data, bytes):
    file_content = mp3_audio_data
  else:
    assert isinstance(mp3_audio_data, io.BytesIO)
    file_content = mp3_audio_data.getvalue()

  # 构造 files 字典
  # 注意：这里的第一个参数是文件名，FastAPI 的 UploadFile 在处理时通常需要一个文件名
  files = {"mp3_audio_file": ("tts_audio.mp3", file_content, "audio/mpeg")}

  data = {
    "text": text,
    "project": project,
    "tts_model": tts_model.value,
    "id_version": id_version,
  }
  timeout = httpx.Timeout(connect=5, read=30, write=30, pool=5)
  response = await get_async_client().post(url, data=data, files=files, headers=headers, timeout=timeout)
  response.raise_for_status()


async def async_gen(
  base_url: str,
  *,
  text: str,
  project: str,
  id_version: TtsIdGenFnVersionT = "v1",
  save_to: str | Path | None = None,
) -> bytes:
  """Return cached audio data"""
  url = f"{base_url.rstrip('/')}/cached-tts/gen"

  # Prepare JSON body data
  json_data = {
    "text": text,
    "project": project,
    "id_version": id_version,
  }

  timeout = httpx.Timeout(connect=5, read=240, write=30, pool=5)
  response = await get_async_client().post(url, json=json_data, timeout=timeout)

  # Raise exception for 4xx/5xx status codes
  response.raise_for_status()

  audio_content = response.content

  # Save to file if path is provided
  if save_to:
    with open(save_to, "wb") as f:
      f.write(audio_content)

  return audio_content


async def async_del(
  base_url: str,
  api_key: str,
  *,
  text: str,
  project: str,
  id_version: TtsIdGenFnVersionT = "v1",
) -> str:
  """Delete cached tts data"""
  url = f"{base_url.rstrip('/')}/cached-tts/del"
  headers = {"X-API-KEY": api_key}

  # Prepare JSON body data
  json_data = {
    "text": text,
    "project": project,
    "id_version": id_version,
  }

  timeout = httpx.Timeout(connect=5, read=240, write=30, pool=5)
  response = await get_async_client().post(url, json=json_data, headers=headers, timeout=timeout)

  # Raise exception for 4xx/5xx status codes
  response.raise_for_status()

  # Return the response text (e.g., "del id=...")
  return response.text
