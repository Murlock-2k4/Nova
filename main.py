from tools.apps import open_app
from tools.music import play_song, pause_music
from tools.weather import get_weather
from tools.calendar_tools import get_todays_events
from tools.alarms import set_wake_alarm, load_saved_alarms
from tools.routines import morning_routine
from voice import listen
from speech import speak
from time_tools import get_current_time
from personality import handle_special_phrases
from brain import ask_nova
from config import WAKE_PHRASES, ACTIVE_TIMEOUT

import state
import msvcrt


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
    lower_text = user_input.lower().strip()

    if lower_text.startswith("open "):
        app_name = user_input[5:].strip()
        result = open_app(app_name)
        print("Nova:", result)
        speak("Opening.")
        return

    if lower_text.startswith("play "):
        song_name = user_input[5:].strip()
        result = play_song(song_name)
        print("Nova:", result)
        speak("Playing.")
        return

    if "weather" in lower_text:
        result = get_weather()
        print("Nova:", result)
        speak(result)
        return

    if "calendar" in lower_text or "schedule" in lower_text:
        result = get_todays_events()
        print("Nova:", result)
        speak(result)
        return

    if lower_text in ["stop music", "music off"]:
        pause_music()
        state.music_is_playing = False
        print("Nova: Music stopped.")
        speak("Music stopped.")
        return
    
    if "wake me up" in lower_text or "set alarm" in lower_text:
        result = set_wake_alarm(user_input)
        print("Nova:", result)
        speak(result)
        return

    if "morning routine" in lower_text:
        print("Nova: Starting morning routine.")
        speak("Starting morning routine.")
        morning_routine()
        return
    
    if "what time" in lower_text or "current time" in lower_text:
        result = get_current_time()
        print("Nova:", result)
        speak(result)
        return

    reply = ask_nova(user_input)
    print("Nova:", reply)
    speak(reply)


def active_session():
    print("Nova: Awake.")
    speak("Yes?")
    
    load_saved_alarms()
    

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

print("Nova is running. Say 'hey nova' to wake me.")
while True:
    # 🎵 MUSIC MODE (no listening unless key pressed)
    if state.music_is_playing:
        action = wait_for_space_or_q()

        if action == "quit":
            print("Nova: Goodbye.")
            speak("Goodbye.")
            break

        # Pause Spotify before listening
        pause_music()
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