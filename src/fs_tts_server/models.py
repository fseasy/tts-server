import asyncio
import subprocess
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime, Dialect, String, Text, TypeDecorator, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import LOGGER as logger
from .config.data_types import TtsModel
from .exceptions import LogicError
from .utils import safe_strftime


def get_db_root_dir() -> Path:
  """Root dir for db"""
  # file structure: ${root}/src/fs_tts_server/models.py
  _db_dir = Path(__file__).parent.parent.parent / "db"

  return _db_dir.absolute()


class CachedAudioFile:
  @staticmethod
  def get_fullpath(relpath: str) -> Path:
    return (get_db_root_dir() / relpath).resolve()

  @staticmethod
  def gen_relpath(id: str, project: str) -> str:
    """File Structure:
    /audios
    /project
    /${id[:2]}
    /${id[2:]}.mp3
    """
    slice_dir_name, fname = id[:2], id[2:]
    return f"audios/{project}/{slice_dir_name}/{fname}.mp3"

  @staticmethod
  async def add(id: str, project: str, mp3_bytes: bytes) -> str:
    """Write bytes to file, return the relative-path to the db root dir
    Exceptions: any possible IO related exceptions
    """
    root_path = get_db_root_dir()
    relpath = CachedAudioFile.gen_relpath(id, project=project)
    full_path = root_path / relpath

    def _write() -> None:
      full_path.parent.mkdir(parents=True, exist_ok=True)
      full_path.write_bytes(mp3_bytes)

    await asyncio.to_thread(_write)
    return relpath

  @staticmethod
  async def remove(relpath: str) -> bool:
    """Use `remove` as del is a python lang keyword"""
    root_path = get_db_root_dir()
    fullpath = root_path / relpath

    def _unlink() -> bool:
      if not fullpath.exists():
        return False
      fullpath.unlink()
      return True

    return await asyncio.to_thread(_unlink)

  @staticmethod
  async def is_valid_audio(relpath: str) -> bool:
    """1. path exists 2. audio content is valid"""
    fullpath = CachedAudioFile.get_fullpath(relpath)

    def _check() -> bool:
      if not fullpath.exists():
        return False
      # decode audio to test if it's fully valid
      cmd = ["ffmpeg", "-v", "error", "-i", str(fullpath), "-f", "null", "-"]
      try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
      except Exception:
        return False

    return await asyncio.to_thread(_check)


def _get_sqlite_db_async_path() -> str:
  db_dir = get_db_root_dir()
  db_dir.mkdir(parents=True, exist_ok=True)  # must create dir, or it will hang without any warning...
  return f"sqlite+aiosqlite:///{db_dir / 'sqlite.db'}"


# you can set `echo=True` for debug
async_engine = create_async_engine(
  _get_sqlite_db_async_path(),
  connect_args={"timeout": 30},  # You must remove  `"autocommit": False` or it will raise exception
)
"""Async engine"""


@event.listens_for(async_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore
  """For Sqlite"""
  # 2. 依赖这里的 isolation_level = None 来禁用底层的隐式事务
  dbapi_connection.isolation_level = None
  cursor = dbapi_connection.cursor()
  try:
    cursor.execute("PRAGMA cache_size=-4000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    # 包裹 journal_mode，遇到别的进程持锁时吞掉异常，不要阻断启动
    cursor.execute("PRAGMA journal_mode=WAL")
  except Exception as e:
    logger.exception(f"sqlite set pragma failed due to exception: {e}")
  finally:
    cursor.close()
  del connection_record


@event.listens_for(async_engine.sync_engine, "begin")
def do_begin(conn) -> None:  # type: ignore
  # 3. 交由 SQLAlchemy 在需要写操作时接管事务
  conn.exec_driver_sql("BEGIN")


AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
"""Async Session maker instance"""


async def create_all_tables() -> None:
  async with async_engine.begin() as conn:
    await conn.run_sync(DbBaseModel.metadata.create_all)


async def drop_all_tables() -> None:
  async with async_engine.begin() as conn:
    await conn.run_sync(DbBaseModel.metadata.drop_all)


async def dispose_engine() -> None:
  """Call this when you need to exit the APP! or the app will hang forever!"""
  try:
    await asyncio.wait_for(async_engine.dispose(), timeout=5.0)
  except Exception as e:
    logger.exception(f"Warning: async_engine.dispose() error/timeout: {e}")


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


class TZDateTime(TypeDecorator[datetime]):
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

  id: Mapped[str] = mapped_column(String(40), primary_key=True)
  """sha1 hex str, length = 40"""
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
