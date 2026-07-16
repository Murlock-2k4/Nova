from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKEN_FILE

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def get_calendar_service():
    creds = None

    if GOOGLE_TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(
            str(GOOGLE_TOKEN_FILE),
            SCOPES,
        )

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            creds = None
            if GOOGLE_TOKEN_FILE.exists():
                GOOGLE_TOKEN_FILE.unlink()

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(GOOGLE_CREDENTIALS_FILE),
            SCOPES,
        )
        creds = flow.run_local_server(port=0)
        GOOGLE_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("calendar", "v3", credentials=creds)


def _parse_event(event: dict[str, Any]) -> dict[str, Any]:
    start_data = event.get("start") or {}
    end_data = event.get("end") or {}
    start_value = start_data.get("dateTime") or start_data.get("date")
    end_value = end_data.get("dateTime") or end_data.get("date")
    all_day = "date" in start_data and "dateTime" not in start_data

    if not start_value:
        start_value = datetime.now().astimezone().isoformat()

    if all_day:
        display_date = datetime.fromisoformat(start_value).strftime("%Y-%m-%d")
        display_time = "All day"
    else:
        local_start = datetime.fromisoformat(start_value.replace("Z", "+00:00")).astimezone()
        display_date = local_start.strftime("%Y-%m-%d")
        display_time = local_start.strftime("%H:%M")

    return {
        "id": event.get("id"),
        "title": event.get("summary") or "Untitled event",
        "description": event.get("description") or "",
        "location": event.get("location") or "",
        "start": start_value,
        "end": end_value,
        "all_day": all_day,
        "display_date": display_date,
        "display_time": display_time,
        "html_link": event.get("htmlLink"),
    }


def get_calendar_events(days: int = 7) -> list[dict[str, Any]]:
    safe_days = max(1, min(31, int(days)))
    service = get_calendar_service()

    now = datetime.now().astimezone()
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    range_end = start_of_today + timedelta(days=safe_days)

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start_of_today.isoformat(),
            timeMax=range_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=100,
        )
        .execute()
    )

    return [_parse_event(event) for event in result.get("items", [])]


def get_todays_events() -> str:
    today = datetime.now().astimezone().date().isoformat()
    events = [
        event for event in get_calendar_events(days=1)
        if event["display_date"] == today
    ]

    if not events:
        return "You have nothing on your calendar today."

    lines = [
        f"{event['display_time']} - {event['title']}"
        for event in events
    ]

    if len(lines) == 1:
        return f"You have 1 event today: {lines[0]}."

    return f"You have {len(lines)} events today: {'; '.join(lines)}."
