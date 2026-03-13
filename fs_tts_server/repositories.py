from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
  AsyncSessionLocal,
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


async def async_create_cached_tts(
  session: AsyncSession,
  id: str,
  text: str,
  project: str,
  tts_model: TtsModel,
  audio_mp3_bytes: bytes,
  do_commit: bool = False,
) -> CachedTts:
  assert lifetime.tzinfo, f"Lifetime tzinfo is None in lifetime: {lifetime}"
  code_data = PrepaidCode(code=code, lifetime=lifetime, has_used=False)
  session.add(code_data)
  if do_commit:
    await session.commit()
  return code_data


async def async_get_cached_tts(session: AsyncSession, code: str, for_update: bool = False) -> CachedTts | None:
  """
  Args:
  - for_update: if True, will lock the row to avoid race-condition
  """
  # may be multiple in rare condition, get the latest one
  stmt = select(PrepaidCode).where(PrepaidCode.code == code).order_by(PrepaidCode.lifetime.desc())
  if for_update:
    stmt = stmt.with_for_update()  # LOCK
  r = await session.execute(stmt)
  return r.scalars().first()
