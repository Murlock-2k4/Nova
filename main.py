from router import route_command
from voice import listen
from speech import speak
from personality import handle_special_phrases
from brain import ask_nova
from config import WAKE_PHRASES, ACTIVE_TIMEOUT
from tools.alarms import load_saved_alarms
from tools.registry import execute_tool

import state
import msvcrt
import logging

from logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def extract_command_from_wake_phrase(text: str):
    lower_text = text.lower().strip()

    for phrase in WAKE_PHRASES:
        if lower_text == phrase:
            return ""

        if lower_text.startswith(phrase + " "):
            return text[len(phrase):].strip(" ,.!?")

        if lower_text.startswith(phrase + ","):
            return text[len(phrase):].strip(" ,.!?")

    return None


def handle_command(user_input: str):
    route_result = route_command(user_input)

    if route_result.handled:
        if route_result.response:
            print("Nova:", route_result.response)
            speak(route_result.response)

        return

    reply = ask_nova(user_input)
    print("Nova:", reply)
    speak(reply)


def active_session():
    print("Nova: Awake.")
    speak("Yes?")
    
    while True:
        user_input = listen(timeout_seconds=ACTIVE_TIMEOUT).strip()

        if not user_input:
            print("Nova: Going back to sleep.")
            return

        lower_text = user_input.lower()

        if lower_text in ["quit", "exit"]:
            print("Nova: Goodbye.")
            speak("Goodbye.")
            raise SystemExit

        if lower_text in ["sleep", "stop listening"]:
            print("Nova: Going back to sleep.")
            speak("Going back to sleep.")
            return

        special_reply = handle_special_phrases(user_input)
        if special_reply:
            print("Nova:", special_reply)
            speak(special_reply)
            continue

        handle_command(user_input)


def wait_for_space_or_q():
    print("🎵 Music mode: press SPACE to talk, Q to quit.")

    while True:
        key = msvcrt.getch()

        if key == b"q":
            return "quit"

        if key == b" ":
            return "talk"

load_saved_alarms()

logger.info("Nova started")
print("Nova is running. Say 'hey Nova' to begin.")

try:
    while True:
        if state.music_is_playing:
            action = wait_for_space_or_q()

            if action == "quit":
                print("Nova: Goodbye.")
                speak("Goodbye.")
                break

            execute_tool("pause_music")
            state.music_is_playing = False

            print("Nova: Listening...")
            heard_text = listen(timeout_seconds=8).strip()

        else:
            heard_text = listen().strip()

        if not heard_text:
            continue

        lower_text = heard_text.lower()

        if lower_text in ["quit", "exit"]:
            print("Nova: Goodbye.")
            speak("Goodbye.")
            break

        special_reply = handle_special_phrases(heard_text)

        if special_reply:
            print("Nova:", special_reply)
            speak(special_reply)
            active_session()
            continue

        command = extract_command_from_wake_phrase(heard_text)

        if command is None:
            continue

        if command == "":
            active_session()
        else:
            print(f"Command: {command}")
            handle_command(command)
            active_session()

except KeyboardInterrupt:
    logger.info("Nova stopped with keyboard interrupt")
    print("\nNova stopped.")

except Exception:
    logger.exception("Unexpected fatal error in Nova")
    print(
        "Nova encountered an unexpected error. "
        "Check logs/nova.log for details."
    )

finally:
    logger.info("Nova shut down")