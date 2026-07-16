from __future__ import annotations

import logging
import threading

import state
from config import ACTIVE_TIMEOUT, WAKE_PHRASES
from conversation_service import process_and_record, record_exchange
from personality import handle_special_phrases
from speech import speak
from tools.registry import execute_tool
from voice import listen

logger = logging.getLogger(__name__)


def extract_command_from_wake_phrase(text: str) -> str | None:
    lower_text = text.lower().strip()

    for phrase in WAKE_PHRASES:
        if lower_text == phrase:
            return ""
        if lower_text.startswith(phrase + " "):
            return text[len(phrase):].strip(" ,.!?")
        if lower_text.startswith(phrase + ","):
            return text[len(phrase):].strip(" ,.!?")

    return None


class VoiceService:
    """Own Nova's wake-word and active-conversation microphone loop."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.is_running:
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="nova-voice-service",
            daemon=True,
        )
        self._thread.start()
        logger.info("Nova voice service started")

    def stop(self, timeout: float = 3.0) -> None:
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

        if self._thread and self._thread.is_alive():
            logger.warning("Nova voice service did not stop before timeout")
        else:
            logger.info("Nova voice service stopped")

        self._thread = None

    def _speak_reply(self, reply: str) -> None:
        print("Nova:", reply)
        speak(reply)

    def _handle_command(self, user_input: str) -> None:
        reply, _ = process_and_record(user_input, source_prefix="voice")
        self._speak_reply(reply)

    def _handle_active_utterance(self, user_input: str) -> bool:
        lower_text = user_input.lower().strip()

        if lower_text in {"quit", "exit", "sleep", "stop listening"}:
            self._speak_reply("Going back to sleep.")
            return False

        special_reply = handle_special_phrases(user_input)
        if special_reply:
            record_exchange(user_input, special_reply, source="voice:special")
            self._speak_reply(special_reply)
            return True

        self._handle_command(user_input)
        return True

    def _active_session(self) -> None:
        print("Nova: Awake.")
        speak("Yes?")

        while not self._stop_event.is_set():
            user_input = listen(
                timeout_seconds=ACTIVE_TIMEOUT,
                stop_event=self._stop_event,
            ).strip()

            if not user_input:
                if not self._stop_event.is_set():
                    print("Nova: Going back to sleep.")
                return

            if not self._handle_active_utterance(user_input):
                return

    def _run(self) -> None:
        print("Nova voice is running. Say 'hey Nova' to begin.")

        try:
            while not self._stop_event.is_set():
                heard_text = listen(stop_event=self._stop_event).strip()
                if not heard_text or self._stop_event.is_set():
                    continue

                # Ambient speech remains invisible. Only a valid wake phrase
                # enters the active conversation and transcript pipeline.
                command = extract_command_from_wake_phrase(heard_text)
                if command is None:
                    continue

                if state.is_music_playing():
                    execute_tool("pause_music")
                    state.set_music_playing(False)

                if command:
                    print(f"Command: {command}")
                    self._handle_command(command)

                self._active_session()
        except Exception as error:
            logger.exception("Nova voice service failed")
            state.set_error(str(error))


voice_service = VoiceService()
