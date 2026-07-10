from datetime import datetime
from zoneinfo import ZoneInfo

from config import TIMEZONE


def get_current_time() -> str:
    now = datetime.now(ZoneInfo(TIMEZONE))
    time_text = now.strftime("%I:%M %p").lstrip("0")
    return f"It is {time_text}."