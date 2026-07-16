from __future__ import annotations

import logging

from brain import ask_nova
from database import save_exchange
from router import route_command
from state import set_error, update_state

logger = logging.getLogger(__name__)


def process_command(command: str) -> tuple[str, str]:
    """Run one Nova command through the shared voice/chat pipeline."""
    cleaned_command = command.strip()
    if not cleaned_command:
        return "I didn't hear a command.", "error"

    update_state(
        status="thinking",
        last_user_message=cleaned_command,
        last_nova_response="",
        current_tool=None,
        last_error=None,
    )

    try:
        route_result = route_command(cleaned_command)
        if route_result.handled:
            response = str(route_result.response or "Command completed.")
            source = "router"
        else:
            response = ask_nova(cleaned_command)
            source = "ai"

        update_state(status="idle", last_nova_response=response)
        return response, source
    except Exception as error:
        logger.exception("Nova command processing failed")
        response = "Nova could not process that request."
        set_error(str(error))
        update_state(last_nova_response=response)
        return response, "error"


def process_and_record(
    command: str,
    *,
    client_id: str | None = None,
    room_id: int | None = None,
    source_prefix: str | None = None,
) -> tuple[str, str]:
    """Process a command and persist the user/assistant exchange."""
    response, source = process_command(command)
    stored_source = f"{source_prefix}:{source}" if source_prefix else source

    try:
        save_exchange(
            command,
            response,
            stored_source,
            client_id=client_id,
            room_id=room_id,
        )
    except Exception:
        logger.exception("Could not save conversation history")

    return response, stored_source


def record_exchange(
    user_message: str,
    assistant_message: str,
    *,
    source: str = "voice",
) -> None:
    """Persist a handled exchange such as a built-in greeting."""
    try:
        save_exchange(user_message, assistant_message, source)
    except Exception:
        logger.exception("Could not save handled voice exchange")
