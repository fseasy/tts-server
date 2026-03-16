from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
  AsyncSessionLocal,
  CachedAudioFile,
  CachedTts,
  TtsModel,
  create_all_tables,
  dispose_engine,
)

if TYPE_CHECKING:
  from fastapi import FastAPI


async def get_db_async_session() -> AsyncGenerator[AsyncSession, Any]:
  """Get a database session.
  To be used for dependency injection.
  copy from: https://github.com/seapagan/fastapi_async_sqlalchemy2_example/blob/main/db.py#L42
  """
  async with AsyncSessionLocal() as session, session.begin():
    yield session


get_db_async_session_cxt = asynccontextmanager(get_db_async_session)
"""Used in out-of fastapi scope or place that can't get connection level session"""


@asynccontextmanager
async def lifespan_db(_: "FastAPI | None") -> AsyncGenerator[Any, None]:
  await create_all_tables()  # create tables if eligible
  yield
  await dispose_engine()  # dispose db after app close!


TtsIdGenFnVersionT = Literal["v1"]


def clean_tts_text(text: str) -> str:
  """Clean tts text before calculate id or save to db"""
  return text.strip()  # a simple preprocess


def gen_cached_tts_id(id_version: TtsIdGenFnVersionT, text: str, project: str) -> str:
  """The tts-id calculation is very important for cached-tts lookup.
  v1: only consider the (text, project), you can view it each (text, project) can only have 1 tts result.
      it's should be like a `default` tts-model result.
  """
  import hashlib

  text = clean_tts_text(text)
  text_hash = hashlib.sha1(text.encode(errors="replace")).hexdigest()
  assert id_version == "v1"
  sig = f"{text_hash}{project}"
  return hashlib.sha1(sig.encode()).hexdigest()


async def async_create_or_update_cached_tts(
  session: AsyncSession,
  id: str,
  text: str,
  project: str,
  tts_model: TtsModel,
  audio_mp3_bytes: bytes,
  do_commit: bool = False,
) -> CachedTts:
  """Will create or update the cached tts record.
  Try to use upsert to keep the atomic.
  """
  relpath = await CachedAudioFile.add(id=id, project=project, mp3_bytes=audio_mp3_bytes)
  record_data = {
    "id": id,
    "text": clean_tts_text(text),
    "project": project,
    "tts_model": tts_model,
    "audio_path": relpath,
  }
  record = CachedTts(**record_data)
  # 动态获取当前数据库的 dialect 并处理
  dialect = session.bind.dialect.name
  if dialect == "sqlite":
    from sqlalchemy.dialects.sqlite import insert

    stmt = insert(CachedTts).values(record_data)
    stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=record_data)
    await session.execute(stmt)

  elif dialect == "postgresql":
    from sqlalchemy.dialects.postgresql import insert

    stmt = insert(CachedTts).values(record_data)
    stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=record_data)
    await session.execute(stmt)

  else:
    # Fallback 到通用 merge (牺牲原子性换取兼容性)
    await session.merge(record)
  if do_commit:
    await session.commit()
  return record


async def async_get_cached_tts(session: AsyncSession, id: str, for_update: bool = False) -> CachedTts | None:
  """
  Args:
  - for_update: if True, will lock the row to avoid race-condition
  """
  stmt = select(CachedTts).where(CachedTts.id == id)
  if for_update:
    stmt = stmt.with_for_update()  # LOCK
  r = await session.execute(stmt)
  return r.scalars().first()


async def async_del_cached_tts(
  session: AsyncSession,
  id: str,
  do_commit: bool = False,
) -> None:
  record = await async_get_cached_tts(session=session, id=id)
  if record is None:
    return
  # 1. first delete audio
  await CachedAudioFile.remove(record.audio_path)
  # 2. delete record
  await session.delete(record)
  if do_commit:
    await session.commit()


async def async_get_project_all_cached_tts(session: AsyncSession, project: str) -> AsyncGenerator[CachedTts, None]:
  """Not safe it cache tts table for this project is too big. But it't ok currently"""
  stmt = select(CachedTts).where(CachedTts.project == project)
  result = await session.stream_scalars(stmt)
  async for r in result:
    yield r
