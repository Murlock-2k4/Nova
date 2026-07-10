from dataclasses import dataclass
from typing import Any

from tools.registry import execute_tool


@dataclass
class RouteResult:
    handled: bool
    response: str | None = None


def route_command(user_input: str) -> RouteResult:
    text = user_input.strip()
    lower_text = text.lower()

    if lower_text.startswith("open "):
        app_name = text[5:].strip()

        return RouteResult(
            handled=True,
            response=execute_tool(
                "open_app",
                {"app_name": app_name},
            ),
        )

    if lower_text.startswith("play "):
        song_request = text[5:].strip()

        return RouteResult(
            handled=True,
            response=execute_tool(
                "play_music",
                {"song_request": song_request},
            ),
        )

    if lower_text in {
        "pause music",
        "stop music",
        "music off",
        "pause spotify",
        "stop spotify",
    }:
        return RouteResult(
            handled=True,
            response=execute_tool("pause_music"),
        )

    if "weather" in lower_text:
        city_name = extract_weather_city(text)

        arguments: dict[str, Any] = {}

        if city_name:
            arguments["city_name"] = city_name

        return RouteResult(
            handled=True,
            response=execute_tool("get_weather", arguments),
        )

    if (
        "calendar" in lower_text
        or "schedule" in lower_text
        or "events today" in lower_text
    ):
        return RouteResult(
            handled=True,
            response=execute_tool("get_calendar"),
        )

    if "what time" in lower_text or "current time" in lower_text:
        return RouteResult(
            handled=True,
            response=execute_tool("get_current_time"),
        )

    if "wake me up" in lower_text or "set alarm" in lower_text:
        return RouteResult(
            handled=True,
            response=execute_tool(
                "set_wake_alarm",
                {"command_text": text},
            ),
        )

    if "morning routine" in lower_text:
        return RouteResult(
            handled=True,
            response=execute_tool("start_morning_routine"),
        )

    if (
        "turn on the lights" in lower_text
        or "turn the lights on" in lower_text
        or lower_text == "lights on"
    ):
        return RouteResult(
            handled=True,
            response=execute_tool("turn_on_lights"),
        )

    return RouteResult(handled=False)


def extract_weather_city(text: str) -> str | None:
    lower_text = text.lower()

    phrases = [
        "weather in ",
        "weather for ",
        "weather at ",
    ]

    for phrase in phrases:
        position = lower_text.find(phrase)

        if position != -1:
            city_start = position + len(phrase)
            city_name = text[city_start:].strip(" ,.!?")

            if city_name:
                return city_name

    return None