import json
import logging
import re
import threading
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import ALARMS_FILE, TIMEZONE
from speech import speak
from tools.routines import morning_routine

logger = logging.getLogger(__name__)
_active_timers: dict[str, threading.Timer] = {}
_timer_lock = threading.Lock()

DAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]
DAY_ALIASES = {
    "monday": 0, "mondays": 0, "mon": 0,
    "tuesday": 1, "tuesdays": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wednesdays": 2, "wed": 2,
    "thursday": 3, "thursdays": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fridays": 4, "fri": 4,
    "saturday": 5, "saturdays": 5, "sat": 5,
    "sunday": 6, "sundays": 6, "sun": 6,
}
NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3,
    "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12,
}


def parse_alarm_clock(text: str) -> tuple[int, int] | None:
    lowered = text.lower()
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?\b", lowered)

    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        period = (match.group(3) or "").replace(".", "")
    else:
        word_match = re.search(
            r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b\s*(a\.?m\.?|p\.?m\.?)?",
            lowered,
        )
        if not word_match:
            return None
        hour = NUMBER_WORDS[word_match.group(1)]
        minute = 0
        period = (word_match.group(2) or "").replace(".", "")

    if minute > 59 or hour > 23 or (period and hour > 12):
        return None
    if period == "pm" and hour != 12:
        hour += 12
    elif period == "am" and hour == 12:
        hour = 0
    return hour, minute


def parse_alarm_days(text: str, default_day: int | None = None) -> list[int]:
    lowered = text.lower()
    if any(phrase in lowered for phrase in ("every day", "daily", "each day")):
        return list(range(7))
    if any(phrase in lowered for phrase in ("weekday", "weekdays", "workday", "workdays")):
        return [0, 1, 2, 3, 4]
    if any(phrase in lowered for phrase in ("weekend", "weekends")):
        return [5, 6]

    selected = {
        index
        for alias, index in DAY_ALIASES.items()
        if re.search(rf"\b{re.escape(alias)}\b", lowered)
    }
    if selected:
        return sorted(selected)

    if default_day is not None:
        return [default_day]
    return list(range(7))


def next_occurrence(alarm: dict, now: datetime | None = None) -> datetime | None:
    if not alarm.get("enabled", True):
        return None

    days = sorted({int(day) for day in alarm.get("days", []) if 0 <= int(day) <= 6})
    if not days:
        return None

    timezone = ZoneInfo(TIMEZONE)
    current = now.astimezone(timezone) if now else datetime.now(timezone)
    hour, minute = map(int, str(alarm["time"]).split(":"))

    for offset in range(8):
        candidate_date = current.date() + timedelta(days=offset)
        if candidate_date.weekday() not in days:
            continue
        candidate = datetime(
            candidate_date.year, candidate_date.month, candidate_date.day,
            hour, minute, tzinfo=timezone,
        )
        if candidate > current:
            return candidate
    return None


def _normalize_alarm(alarm: dict) -> dict | None:
    timezone = ZoneInfo(TIMEZONE)
    raw_time = alarm.get("time")
    if not raw_time:
        return None

    days = alarm.get("days")
    clock_time = str(raw_time)

    # Migrate the former one-off ISO datetime format to a weekly alarm.
    if "T" in clock_time:
        try:
            old_datetime = datetime.fromisoformat(clock_time)
            if old_datetime.tzinfo is None:
                old_datetime = old_datetime.replace(tzinfo=timezone)
            old_datetime = old_datetime.astimezone(timezone)
            clock_time = old_datetime.strftime("%H:%M")
            days = [old_datetime.weekday()]
        except ValueError:
            return None

    try:
        hour, minute = map(int, clock_time.split(":"))
    except (ValueError, AttributeError):
        return None
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None

    normalized_days = sorted({int(day) for day in (days or []) if 0 <= int(day) <= 6})
    if not normalized_days:
        normalized_days = list(range(7))

    return {
        "id": str(alarm.get("id") or uuid.uuid4()),
        "time": f"{hour:02d}:{minute:02d}",
        "days": normalized_days,
        "enabled": bool(alarm.get("enabled", True)),
        "type": str(alarm.get("type") or "morning_routine"),
        "label": str(alarm.get("label") or "Morning routine"),
        "created_at": str(alarm.get("created_at") or datetime.now(timezone).isoformat()),
    }


def load_alarms() -> list[dict]:
    if not ALARMS_FILE.exists():
        return []
    try:
        raw = json.loads(ALARMS_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        normalized = [item for alarm in raw if isinstance(alarm, dict) and (item := _normalize_alarm(alarm))]
        if normalized != raw:
            save_alarms(normalized)
        return normalized
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        logger.exception("Could not load alarms")
        return []


def save_alarms(alarms: list[dict]) -> None:
    ALARMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALARMS_FILE.write_text(json.dumps(alarms, indent=4), encoding="utf-8")


def _public_alarm(alarm: dict) -> dict:
    occurrence = next_occurrence(alarm)
    return {
        **alarm,
        "day_names": [DAY_NAMES[day] for day in alarm["days"]],
        "next_occurrence": occurrence.isoformat() if occurrence else None,
        "seconds_remaining": max(0, int((occurrence - datetime.now(ZoneInfo(TIMEZONE))).total_seconds())) if occurrence else None,
    }


def list_alarms() -> list[dict]:
    alarms = [_public_alarm(alarm) for alarm in load_alarms()]
    return sorted(
        alarms,
        key=lambda item: (
            not item["enabled"],
            item["next_occurrence"] or "9999",
            item["time"],
        ),
    )


def remove_alarm(alarm_id: str) -> bool:
    alarms = load_alarms()
    updated = [alarm for alarm in alarms if alarm["id"] != alarm_id]
    if len(updated) == len(alarms):
        return False
    save_alarms(updated)
    with _timer_lock:
        timer = _active_timers.pop(alarm_id, None)
    if timer:
        timer.cancel()
    return True


def update_alarm(alarm_id: str, *, enabled: bool | None = None) -> dict | None:
    alarms = load_alarms()
    target = None
    for alarm in alarms:
        if alarm["id"] == alarm_id:
            if enabled is not None:
                alarm["enabled"] = bool(enabled)
            target = alarm
            break
    if target is None:
        return None

    save_alarms(alarms)
    with _timer_lock:
        timer = _active_timers.pop(alarm_id, None)
    if timer:
        timer.cancel()
    if target["enabled"]:
        schedule_alarm(target)
    return _public_alarm(target)


def run_alarm(alarm_id: str) -> None:
    alarm = next((item for item in load_alarms() if item["id"] == alarm_id), None)
    if not alarm or not alarm.get("enabled", True):
        return

    with _timer_lock:
        _active_timers.pop(alarm_id, None)

    result = morning_routine()
    logger.info("Weekly alarm %s triggered", alarm_id)
    print("Nova:", result)
    speak(result)

    # It remains saved; schedule its next selected weekday.
    schedule_alarm(alarm)


def schedule_alarm(alarm: dict) -> bool:
    occurrence = next_occurrence(alarm)
    if occurrence is None:
        return False

    seconds_until_alarm = (occurrence - datetime.now(ZoneInfo(TIMEZONE))).total_seconds()
    if seconds_until_alarm <= 0:
        return False

    alarm_id = alarm["id"]
    timer = threading.Timer(seconds_until_alarm, run_alarm, args=[alarm_id])
    timer.daemon = True
    with _timer_lock:
        previous = _active_timers.pop(alarm_id, None)
        if previous:
            previous.cancel()
        _active_timers[alarm_id] = timer
    timer.start()
    logger.info("Scheduled alarm %s for %s", alarm_id, occurrence.isoformat())
    return True


def create_alarm(
    time_value: str,
    days: list[int],
    label: str = "Morning routine",
    enabled: bool = True,
) -> dict:
    match = re.fullmatch(r"(\d{2}):(\d{2})", time_value.strip())
    if not match:
        raise ValueError("Alarm time must use HH:MM format")
    hour, minute = int(match.group(1)), int(match.group(2))
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Invalid alarm time")

    normalized_days = sorted({int(day) for day in days if 0 <= int(day) <= 6})
    if not normalized_days:
        raise ValueError("Select at least one weekday")

    timezone = ZoneInfo(TIMEZONE)
    alarm = {
        "id": str(uuid.uuid4()),
        "time": f"{hour:02d}:{minute:02d}",
        "days": normalized_days,
        "enabled": bool(enabled),
        "type": "morning_routine",
        "label": label.strip() or "Morning routine",
        "created_at": datetime.now(timezone).isoformat(),
    }
    alarms = load_alarms()
    alarms.append(alarm)
    save_alarms(alarms)
    if alarm["enabled"]:
        schedule_alarm(alarm)
    return _public_alarm(alarm)


def _describe_days(days: list[int]) -> str:
    if days == list(range(7)):
        return "every day"
    if days == [0, 1, 2, 3, 4]:
        return "every weekday"
    if days == [5, 6]:
        return "on weekends"
    return "on " + ", ".join(DAY_NAMES[day] for day in days)


def set_wake_alarm(command_text: str) -> str:
    clock = parse_alarm_clock(command_text)
    if clock is None:
        return "I couldn't understand the alarm time."

    now = datetime.now(ZoneInfo(TIMEZONE))
    days = parse_alarm_days(command_text, default_day=now.weekday())
    alarm = create_alarm(f"{clock[0]:02d}:{clock[1]:02d}", days)
    occurrence = datetime.fromisoformat(alarm["next_occurrence"])
    time_text = occurrence.strftime("%I:%M %p").lstrip("0")
    return f"Alarm set for {time_text} {_describe_days(days)}."


def load_saved_alarms() -> None:
    alarms = load_alarms()
    loaded = 0
    for alarm in alarms:
        if alarm.get("enabled", True) and schedule_alarm(alarm):
            loaded += 1
    if loaded:
        logger.info("Loaded %d weekly alarm(s)", loaded)
