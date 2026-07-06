import json
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from tools.routines import morning_routine

TIMEZONE = ZoneInfo("America/Denver")
BASE_DIR = Path(__file__).resolve().parent
ALARMS_FILE = BASE_DIR / "alarms.json"

active_timers = []

NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}

def parse_wake_time(text: str):
    text = text.lower()

    # First try normal digit time: 8, 8:30, 8 am, 8:30 pm
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)

    # If no digit time, try word time: eight am, seven pm, twelve
    if not match:
        word_match = re.search(
            r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b\s*(am|pm)?",
            text
        )

        if not word_match:
            return None

        hour = NUMBER_WORDS[word_match.group(1)]
        minute = 0
        period = word_match.group(2)

    else:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        period = match.group(3)

    if period == "pm" and hour != 12:
        hour += 12

    if period == "am" and hour == 12:
        hour = 0

    now = datetime.now(TIMEZONE)

    alarm_time = now.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )

    if alarm_time <= now:
        alarm_time += timedelta(days=1)

    return alarm_time


def load_alarms():
    if not ALARMS_FILE.exists():
        return []

    try:
        with open(ALARMS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return []


def save_alarms(alarms):
    with open(ALARMS_FILE, "w", encoding="utf-8") as file:
        json.dump(alarms, file, indent=4)


def remove_alarm(alarm_time_iso: str):
    alarms = load_alarms()
    alarms = [alarm for alarm in alarms if alarm["time"] != alarm_time_iso]
    save_alarms(alarms)


def run_alarm(alarm_time_iso: str):
    remove_alarm(alarm_time_iso)
    morning_routine()


def schedule_alarm(alarm_time: datetime):
    now = datetime.now(TIMEZONE)
    seconds_until_alarm = (alarm_time - now).total_seconds()

    if seconds_until_alarm <= 0:
        return

    alarm_time_iso = alarm_time.isoformat()

    timer = threading.Timer(seconds_until_alarm, run_alarm, args=[alarm_time_iso])
    timer.daemon = True
    timer.start()

    active_timers.append(timer)


def set_wake_alarm(command_text: str) -> str:
    alarm_time = parse_wake_time(command_text)

    if not alarm_time:
        return "I couldn't understand the wake up time."

    alarms = load_alarms()

    alarms.append({
        "time": alarm_time.isoformat(),
        "type": "morning_routine"
    })

    save_alarms(alarms)
    schedule_alarm(alarm_time)

    time_text = alarm_time.strftime("%I:%M %p").lstrip("0")

    return f"Wake up routine set for {time_text}."


def load_saved_alarms():
    alarms = load_alarms()
    now = datetime.now(TIMEZONE)
    updated_alarms = []

    for alarm in alarms:
        alarm_time = datetime.fromisoformat(alarm["time"])

        if alarm_time > now:
            schedule_alarm(alarm_time)
            updated_alarms.append(alarm)

    save_alarms(updated_alarms)

    if updated_alarms:
        print(f"Nova: Loaded {len(updated_alarms)} saved alarm(s).")