from collections.abc import Callable
from typing import Any

from tools.apps import open_app
from tools.music import play_song, pause_music
from tools.weather import get_weather
from tools.calendar_tools import get_todays_events
from tools.alarms import set_wake_alarm
from tools.routines import morning_routine
from tools.lights import turn_on_lights
from time_tools import get_current_time


def run_morning_routine() -> str:
    return morning_routine()


TOOLS: dict[str, dict[str, Any]] = {
    "open_app": {
        "description": "Open an installed application on the Windows computer.",
        "function": open_app,
        "parameters": {
            "app_name": {
                "type": "string",
                "description": "The name of the application to open.",
                "required": True,
            }
        },
    },

    "play_music": {
        "description": "Search for and play a song using Spotify.",
        "function": play_song,
        "parameters": {
            "song_request": {
                "type": "string",
                "description": (
                    "The song name, optionally followed by the artist. "
                    "For example: Starboy by The Weeknd."
                ),
                "required": True,
            }
        },
    },

    "pause_music": {
        "description": "Pause the currently playing Spotify music.",
        "function": pause_music,
        "parameters": {},
    },

    "get_weather": {
        "description": "Get today's weather for the configured home city.",
        "function": get_weather,
        "parameters": {
            "city_name": {
                "type": "string",
                "description": (
                    "Optional city name. Leave empty to use the configured "
                    "home city."
                ),
                "required": False,
            }
        },
    },

    "get_calendar": {
        "description": "Get today's events from the user's Google Calendar.",
        "function": get_todays_events,
        "parameters": {},
    },

    "set_wake_alarm": {
        "description": (
            "Set a wake-up alarm that starts Nova's morning routine."
        ),
        "function": set_wake_alarm,
        "parameters": {
            "command_text": {
                "type": "string",
                "description": (
                    "A time request such as 'wake me up at eight thirty am'."
                ),
                "required": True,
            }
        },
    },

    "start_morning_routine": {
        "description": (
            "Start the morning routine immediately, including lights, "
            "weather and calendar."
        ),
        "function": run_morning_routine,
        "parameters": {},
    },

    "turn_on_lights": {
        "description": "Turn on the configured smart lights.",
        "function": turn_on_lights,
        "parameters": {},
    },

    "get_current_time": {
        "description": "Get the current time in Nova's configured timezone.",
        "function": get_current_time,
        "parameters": {},
    },
}

def get_tool(tool_name: str) -> dict[str, Any] | None:
    return TOOLS.get(tool_name)


def get_tool_descriptions() -> str:
    lines = []

    for name, tool in TOOLS.items():
        lines.append(f"- {name}: {tool['description']}")

    return "\n".join(lines)


def execute_tool(tool_name: str, arguments: dict[str, Any] | None = None):
    tool = get_tool(tool_name)

    if tool is None:
        return f"Unknown tool: {tool_name}"

    function: Callable = tool["function"]
    arguments = arguments or {}

    try:
        return function(**arguments)
    except TypeError as error:
        return f"Invalid arguments for {tool_name}: {error}"
    except Exception as error:
        print(f"Tool error [{tool_name}]: {error}")
        return f"The {tool_name} tool failed."