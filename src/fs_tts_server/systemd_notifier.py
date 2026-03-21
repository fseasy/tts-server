"""watchdog for systemd.

1. in systemd service. set:
   Type=notify

   WatchdogSec=30
   Restart=always
2. put the
"""

import asyncio
import logging
import os
import socket
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from .config import LOGGER as logger
from .models import async_engine


@asynccontextmanager
async def systemd_notifier_lifespan(
  app: FastAPI, async_db_engine: AsyncEngine | None = None
) -> AsyncGenerator[Any, None]:
  """Please call this after you do anything else! because it'll send `READY/STOPPING` signal"""
  del app
  # 启动看门狗后台任务
  task = asyncio.create_task(_db_watchdog_task())
  # 发送启动成功
  _send_sd_notify("READY=1")
  try:
    yield
  finally:
    _send_sd_notify("STOPPING=1")

    try:
      task.cancel()
    except asyncio.CancelledError:
      pass  # 预期的取消异常
    logger.info("systemd: db watchdog stopped.")


async def _db_watchdog_task() -> None:
  """后台监控任务：定期执行 SQL 任务，确保 SQL 运行正常，并喂狗"""
  interval_usec = os.getenv("WATCHDOG_USEC")
  if not interval_usec:
    logger.warning("watchdog isn't set in systemd. skip watchdog task")
    return
  watch_sleep_sec = round(int(interval_usec) / 1_000_000 / 3)  # try to report 3 times in one watch duration
  _send_sd_notify(f"STATUS=prepared to create systemd watchdog task, report interval={watch_sleep_sec}s")
  while True:
    try:
      async with async_engine.begin() as conn:
        await conn.exec_driver_sql("SELECT 1")

      # 2. 如果成功执行，说明事件循环没死，DB 没卡死，通知 Systemd
      _send_sd_notify("WATCHDOG=1")

    except Exception as e:
      # 如果连不上 DB 报错，故意不喂狗，让 Systemd 几秒后重启我们
      logger.exception(f"Watchdog health check failed: {e}")

    await asyncio.sleep(watch_sleep_sec)


def _send_sd_notify(data: str):
  # 读取拦截后的 Socket 地址
  addr = os.getenv("CUSTOM_NOTIFY_SOCKET")
  if not addr:
    return
  if addr.startswith("@"):
    addr = "\0" + addr[1:]
  try:
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
      sock.connect(addr)
      sock.sendall(data.encode())
  except Exception as e:
    logger.warning(f"Failed to send watchdog signal to systemd: {e}")
