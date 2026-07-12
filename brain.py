import logging
from typing import Any
import re

import requests

from config import (
    OLLAMA_CHAT_URL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
)
from tools.registry import execute_tool, get_ollama_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are Nova, a local smart-home voice assistant.

Reply briefly, clearly, and naturally.

Only call a tool when the user clearly requests an action or asks for
live, personal, or device-specific information.

Use tools for:
- current weather or forecasts
- current time
- the user's calendar
- Spotify playback
- setting alarms
- opening applications
- controlling lights
- starting routines

Do NOT call tools for:
- greetings such as "how are you?"
- general knowledge questions
- definitions such as "what is blue?"
- opinions
- casual conversation
- explanations

Examples:

User: How are you today?
Assistant: I'm doing well. How can I help?

User: What is blue?
Assistant: Blue is a color in the visible spectrum.

User: What's the weather today?
Assistant: Call get_weather.

User: Do I have anything planned today?
Assistant: Call get_calendar.

User: Could you play some jazz?
Assistant: Call play_music.

If no tool clearly applies, answer normally.
Never call a loosely related tool.
"""


def remove_thinking(text: str) -> str:
    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if "</think>" in text:
        text = text.split("</think>", 1)[-1]

    return text.strip()


def ask_nova(user_text: str) -> str:
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_text,
        },
    ]

    try:
        response = requests.post(
            OLLAMA_CHAT_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "tools": get_ollama_tools(),
                "stream": False,
                "keep_alive": OLLAMA_KEEP_ALIVE,
            },
            timeout=60,
        )

        response.raise_for_status()
        data = response.json()

        message: dict[str, Any] = data.get("message", {})
        tool_calls = message.get("tool_calls") or []

        if tool_calls:
            results = []

            for tool_call in tool_calls:
                function_data = tool_call.get("function", {})
                tool_name = function_data.get("name", "")
                arguments = function_data.get("arguments", {})

                if not isinstance(arguments, dict):
                    arguments = {}

                logger.info(
                    "AI selected tool=%s arguments=%s",
                    tool_name,
                    arguments,
                )

                if not tool_call_is_valid(user_text, tool_name):
                    logger.warning(
                        "Rejected invalid AI tool selection: tool=%s user_text=%s",
                        tool_name,
                        user_text,
                    )

                    return ask_without_tools(user_text)

                result = execute_tool(tool_name, arguments)

                if result:
                    results.append(str(result))

            if results:
                return " ".join(results)

            return "The requested action did not return a result."

        content = remove_thinking(message.get("content", "")
)

        if content:
            return content

        logger.warning("Ollama returned neither content nor tool calls")
        return "I didn't receive a usable response."

    except requests.ConnectionError:
        logger.exception("Could not connect to Ollama")
        return "I can't reach Ollama. Please check whether it is running."

    except requests.Timeout:
        logger.exception("Ollama request timed out")
        return "My language model took too long to respond."

    except requests.RequestException:
        logger.exception("Ollama request failed")
        return "Something went wrong while contacting my language model."

    except (KeyError, TypeError, ValueError):
        logger.exception("Invalid Ollama tool response")
        return "I received an invalid response from my language model."
    
def tool_call_is_valid(
    user_text: str,
    tool_name: str,
) -> bool:
    text = user_text.lower()

    rules = {
        "get_weather": (
            "weather",
            "forecast",
            "temperature",
            "rain",
            "snow",
        ),
        "get_current_time": (
            "what time",
            "current time",
            "time is it",
        ),
        "get_calendar": (
            "calendar",
            "schedule",
            "planned",
            "events",
            "appointments",
        ),
        "play_music": (
            "play",
            "music",
            "song",
            "spotify",
            "listen to",
        ),
        "pause_music": (
            "pause",
            "stop music",
            "stop spotify",
        ),
        "open_app": (
            "open",
            "launch",
            "start app",
        ),
        "set_wake_alarm": (
            "alarm",
            "wake me",
            "wake up",
        ),
        "start_morning_routine": (
            "morning routine",
            "start my morning",
        ),
        "turn_on_lights": (
            "light",
            "lights",
            "lamp",
        ),
    }

    keywords = rules.get(tool_name)

    if keywords is None:
        return False

    return any(keyword in text for keyword in keywords)

def ask_without_tools(user_text: str) -> str:
    response = requests.post(
        OLLAMA_CHAT_URL,
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Nova, a concise and friendly assistant. "
                        "Answer the user's question directly in one or two "
                        "sentences. Do not mention or call tools."
                    ),
                },
                {
                    "role": "user",
                    "content": user_text,
                },
            ],
            "stream": False,
            "keep_alive": "30m",
        },
        timeout=60,
    )

    response.raise_for_status()

    return response.json()["message"]["content"].strip()