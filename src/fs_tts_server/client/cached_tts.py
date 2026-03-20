import io
import json
from pathlib import Path

import httpx
from pydantic import BaseModel

from fs_tts_server.config import LOGGER as logger
from fs_tts_server.config.data_types import TtsModel
from fs_tts_server.repositories import TtsIdGenFnVersionT


class CachedTtsListData(BaseModel):
  text: str
  project: str
  tts_model: TtsModel
  is_valid_audio: bool


async def async_list(base_url: str, api_key: str, *, project: str) -> list[CachedTtsListData]:
  API = "/cached-tts/list"
  url = f"{base_url.rstrip('/')}{API}"
  headers = {"X-API-KEY": api_key}
  data = {"project": project}

  server_data: list[CachedTtsListData] = []
  async with httpx.AsyncClient() as client:
    async with client.stream("POST", url, json=data, headers=headers) as response:
      try:
        response.raise_for_status()
      except httpx.HTTPStatusError as e:
        try:
          content = (await response.aread()).decode()
        except Exception as ex:
          content = f"none due to exception: {ex}"
        logger.critical(f"Request `/cache-tts/list` failed: Status code: {e.response.status_code} content: {content}")
        raise
      async for line in response.aiter_lines():
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

  async with httpx.AsyncClient() as client:
    response = await client.post(url, data=data, files=files, headers=headers, timeout=30.0)
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

  async with httpx.AsyncClient() as client:
    # FastAPI parses the Pydantic model from the JSON body
    response = await client.post(url, json=json_data, timeout=30.0)

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

  async with httpx.AsyncClient() as client:
    # POST request with JSON body
    # httpx .post() supports json parameter in modern versions
    response = await client.post(url, json=json_data, headers=headers, timeout=30.0)

    # Raise exception for 4xx/5xx status codes
    response.raise_for_status()

    # Return the response text (e.g., "del id=...")
    return response.text
