import traceback
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession


from fs_tts_server import config
from fs_tts_server.exceptions import InvalidUserInputException, LogicError
from fs_tts_server.models import TtsModel
from fs_tts_server.repositories import gen_cached_tts_id, get_db_async_session, async_get_cached_tts


# We define the routers to group api endpoints and support future expansion.
cached_tts_router = APIRouter(prefix="/cached-tts", tags=["CachedTts"])


class CachedTtsGenReq(BaseModel):
  text: str
  project: str
  tts_model: TtsModel
  version: Literal["v1"] = "v1"


@cached_tts_router.get("/gen")
async def gen_cached_tts(
  req: CachedTtsGenReq,
  db_session: AsyncSession = Depends(get_db_async_session),
):
  id = gen_cached_tts_id(text=req.text, project=req.project, tts_model=req.tts_model, version=req.version)
  data = await async_get_cached_tts(session=db_session, id=id)
  if not data:
    ...
  relpath = data.audio_path
