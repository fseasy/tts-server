import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from fs_tts_server.config.data_types import TtsModel
from fs_tts_server.header_auth import verify_api_key
from fs_tts_server.models import CachedAudioFile, CachedTts
from fs_tts_server.repositories import (
  TtsIdGenFnVersionT,
  async_create_or_update_cached_tts,
  async_del_cached_tts,
  async_get_cached_tts,
  async_get_project_all_cached_tts,
  gen_cached_tts_id,
  get_db_async_session,
)

# We define the routers to group api endpoints and support future expansion.
cached_tts_router = APIRouter(prefix="/cached-tts", tags=["CachedTts"])


class CachedTtsBaseReq(BaseModel):
  id_version: TtsIdGenFnVersionT = "v1"
  text: str
  project: str


@cached_tts_router.post("/gen")
async def gen_cached_tts(
  req: CachedTtsBaseReq,
  db_session: AsyncSession = Depends(get_db_async_session),
) -> FileResponse:
  """Return Audio stream if audio exists"""
  id = gen_cached_tts_id(text=req.text, project=req.project, id_version=req.id_version)
  data = await async_get_cached_tts(session=db_session, id=id)
  if not data:
    raise HTTPException(status_code=404, detail=f"id {id} not exist in db")
  relpath = data.audio_path
  audio_full_path = CachedAudioFile.get_fullpath(relpath)
  if not audio_full_path.exists():
    raise HTTPException(status_code=404, detail=f"id {id} exists in db while audio {audio_full_path} not exist")
  return FileResponse(audio_full_path, media_type="audio/mpeg")


@cached_tts_router.post("/add", dependencies=[Depends(verify_api_key)])
async def add_cached_tts(
  db_session: AsyncSession = Depends(get_db_async_session),
  text: str = Form(...),
  project: str = Form(...),
  tts_model: TtsModel = Form(...),
  mp3_audio_file: UploadFile = File(...),
  id_version: TtsIdGenFnVersionT = Form("v1"),
) -> Response:
  audio_mp3_bytes = await mp3_audio_file.read()
  id = gen_cached_tts_id(text=text, project=project, id_version=id_version)
  await async_create_or_update_cached_tts(
    session=db_session, id=id, text=text, project=project, tts_model=tts_model, audio_mp3_bytes=audio_mp3_bytes
  )
  return Response(status_code=200, content=f"add id={id}")


@cached_tts_router.post("/del", dependencies=[Depends(verify_api_key)])
async def del_cached_tts(
  req: CachedTtsBaseReq,
  db_session: AsyncSession = Depends(get_db_async_session),
) -> Response:
  id = gen_cached_tts_id(text=req.text, project=req.project, id_version=req.id_version)
  await async_del_cached_tts(session=db_session, id=id)
  return Response(content=f"del id={id}", status_code=200)


class CachedTtsListReq(BaseModel):
  project: str


@cached_tts_router.post("/list", dependencies=[Depends(verify_api_key)])
async def list_cached_tts(
  req: CachedTtsListReq,
  db_session: AsyncSession = Depends(get_db_async_session),
) -> StreamingResponse:
  """A streaming response.
  - read example in client:

    ```Python
    import httpx

    async def fetch_tts_stream():
      async with httpx.AsyncClient() as client:
        async with client.stream("GET", "http://your-api/list", json={"project": "test"}) as response:
          async for line in response.aiter_lines():
            if line:
              data = json.loads(line)
              print(f"收到记录: {data['id']}")
    ```
  """

  async def cached_tts2tgt_dict(record: CachedTts) -> dict[str, Any]:
    return {
      "text": record.text,
      "tts_model": record.tts_model.value,
      "is_valid_audio": await CachedAudioFile.is_valid_audio(record.audio_path),
    }

  async def generate_tts_stream() -> AsyncGenerator[str, None]:
    async for tts_record in async_get_project_all_cached_tts(db_session, req.project):
      # to jsonl
      yield json.dumps(await cached_tts2tgt_dict(tts_record)) + "\n"

  return StreamingResponse(
    generate_tts_stream(),
    media_type="application/x-ndjson",  # NDJSON (Newline Delimited JSON)
  )
