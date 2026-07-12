from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any


@dataclass
class AssistantState:
    status: str = "idle"
    is_speaking: bool = False
    music_is_playing: bool = False

    last_user_message: str = ""
    last_nova_response: str = ""

    current_tool: str | None = None
    last_error: str | None = None

    updated_at: str = ""


StateListener = Callable[[dict[str, Any]], None]

_state = AssistantState()
_state_lock = Lock()
_listeners: set[StateListener] = set()
_listeners_lock = Lock()


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_state_listener(listener: StateListener) -> None:
    """Register a callback that receives a snapshot after every state change."""
    with _listeners_lock:
        _listeners.add(listener)


def remove_state_listener(listener: StateListener) -> None:
    with _listeners_lock:
        _listeners.discard(listener)


def _notify_listeners(snapshot: dict[str, Any]) -> None:
    # Copy the listeners so callbacks run without holding Nova's state locks.
    with _listeners_lock:
        listeners = tuple(_listeners)

    for listener in listeners:
        try:
            listener(snapshot.copy())
        except Exception:
            # State updates must never fail because a dashboard listener failed.
            continue


def update_state(**changes: Any) -> None:
    with _state_lock:
        for name, value in changes.items():
            if not hasattr(_state, name):
                raise ValueError(f"Unknown state field: {name}")

            setattr(_state, name, value)

        _state.updated_at = _current_timestamp()
        snapshot = asdict(_state)

    _notify_listeners(snapshot)


def get_state() -> dict[str, Any]:
    with _state_lock:
        return asdict(_state)


def set_status(status: str) -> None:
    update_state(status=status)


def set_speaking(value: bool) -> None:
    update_state(
        is_speaking=value,
        status="speaking" if value else "idle",
    )


def is_speaking() -> bool:
    with _state_lock:
        return _state.is_speaking


def set_music_playing(value: bool) -> None:
    update_state(music_is_playing=value)


def is_music_playing() -> bool:
    with _state_lock:
        return _state.music_is_playing


def set_error(message: str | None) -> None:
    update_state(
        last_error=message,
        status="error" if message else "idle",
    )