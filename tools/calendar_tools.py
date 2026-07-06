from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

BASE_DIR = Path(__file__).resolve().parent
TOKEN_FILE = BASE_DIR / "token.json"
CREDENTIALS_FILE = BASE_DIR / "credentials.json"


def get_calendar_service():
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("calendar", "v3", credentials=creds)


def get_todays_events() -> str:
    service = get_calendar_service()

    now = datetime.now().astimezone()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = events_result.get("items", [])

    if not events:
        return "You have nothing on your calendar today."

    lines: List[str] = []

    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        title = event.get("summary", "Untitled event")

        if "T" in start:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone()
            time_text = dt.strftime("%H:%M")
            lines.append(f"{time_text} - {title}")
        else:
            lines.append(f"All day - {title}")

    if len(lines) == 1:
        return f"You have 1 event today: {lines[0]}."

    joined = "; ".join(lines)
    return f"You have {len(lines)} events today: {joined}."