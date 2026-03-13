from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime, Dialect, String, Text, TypeDecorator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .exceptions import LogicError
from .utils import safe_strftime


def get_db_root_dir() -> Path:
  """Root dir for db"""
  _db_dir = Path(__file__).parent

  return _db_dir.absolute()


# Define enums
class TtsModel(StrEnum):
  PUBLIC = "public"

  def locale_name(self) -> str:
    m = {TtsModel.PUBLIC: "公共"}
    return m[self]


def _get_sqlite_db_async_path() -> str:
  db_dir = get_db_root_dir()
  return f"sqlite+aiosqlite:///{db_dir / 'sqlite.db'}"


# you can set `echo=True` for debug
async_engine = create_async_engine(_get_sqlite_db_async_path())
"""Async engine"""

AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
"""Async Session maker instance"""


class StrEnumDecorator(TypeDecorator):  # type: ignore
  """Save StrEnum as str in DB, but read as StrEnum as Python."""

  impl = String  # tell the the impl

  def __init__(self, enum_class: type[StrEnum], *args: Any, **kwargs: Any):
    super().__init__(*args, **kwargs)
    self.enum_class = enum_class

  def process_bind_param(self, value: None | StrEnum, dialect: Dialect) -> str | None:
    """write"""
    del dialect
    if value is None:
      return None
    if isinstance(value, self.enum_class):
      return value.value
    return value

  def process_result_value(self, value: str | None, dialect: Dialect) -> StrEnum | None:
    """read"""
    del dialect
    if value is None:
      return None
    return self.enum_class(value)


class TZDateTime(TypeDecorator):
  """Save & Load always keep the UTC tz.
  - in DB: no tz info
  - in application: always has tz

  WHY: make no-tz info has better compatibility across different db (sqlite didn't reserve tz info)

  write-flow: 1. assert input has tz. 2. transform to utc tz 3. remove tz and put to db
  read-flow: 1. read from db, add utc tz
  """

  # ! impl type, This is Datetime without TZ.
  # Tips: DateTime(timezone=True) let the db create datetime with tz. But sqlite don't support it.
  impl = DateTime
  cache_ok = True  # allow SQLAlchemy cache

  def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
    """write flow: transform to UTC, then remove tz info"""
    if value is None:
      return None
    if not value.tzinfo:
      raise LogicError(f"DB input time must have tz info while [{value}] doesn't have")

    utc_value = value.astimezone(ZoneInfo("UTC"))
    clean_value = utc_value.replace(tzinfo=None)
    return clean_value  # noqa: RET504

  def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
    """read flow: add UTC tz info"""
    if value is None:
      return None
    return value.replace(tzinfo=ZoneInfo("UTC"))  # noqa: UP017


class DbBaseModel(DeclarativeBase):
  pass


class CachedTts(DbBaseModel):
  __tablename__ = "cached_tts"

  id: Mapped[str] = mapped_column(String(36), primary_key=True)
  text: Mapped[str] = mapped_column(Text)
  project: Mapped[str] = mapped_column(String(30), index=True)
  tts_model: Mapped[TtsModel] = mapped_column(StrEnumDecorator(TtsModel), index=True)
  audio_path: Mapped[str] = mapped_column(Text)
  # datetime In UTC tz while don't contain tz info
  updated_at: Mapped[datetime] = mapped_column(
    TZDateTime,
    default=lambda: datetime.now(tz=UTC),
    onupdate=lambda: datetime.now(tz=UTC),
  )

  def __str__(self) -> str:
    # no relationship print
    return (
      f"User(id=[{self.id}], text=[{self.text}], project=[{self.project}]"
      f", tts_model=[{self.tts_model.name}]"
      f", audio_path=[{self.audio_path}]"
      f", updated_at=[{safe_strftime(self.updated_at)}]"
      ")"
    )


async def create_all_tables() -> None:
  async with async_engine.begin() as conn:
    await conn.run_sync(DbBaseModel.metadata.create_all)


async def drop_all_tables() -> None:
  async with async_engine.begin() as conn:
    await conn.run_sync(DbBaseModel.metadata.drop_all)


async def dispose_engine() -> None:
  """Call this when you need to exit the APP! or the app will hang forever!"""
  await async_engine.dispose()
