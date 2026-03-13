from datetime import datetime
from zoneinfo import ZoneInfo


def safe_strftime(t: datetime | None) -> str:
  if t is None:
    return "null"
  target_zone = ZoneInfo("Asia/Shanghai")
  return t.astimezone(target_zone).strftime("%Y/%m%d %H:%M %z")
