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

When the user asks for an action that matches an available tool,
call that tool instead of pretending to perform the action.

Use tools for live or personal information such as:
- weather
- current time
- calendar
- Spotify
- alarms
- applications
- lights
- morning routines

For ordinary knowledge questions, answer directly without calling a tool.

Do not claim that a tool succeeded unless the tool result says it succeeded.

Do not show your internal reasoning or analysis.
Return only the final answer or a tool call.
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