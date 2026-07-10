import threading
import subprocess
from pathlib import Path
import winsound
import time
import state
from config import PIPER_MODEL_PATH, PIPER_OUTPUT_FILE


def _speak_blocking(text: str):
    state.is_speaking = True

    try:
        subprocess.run(
            [
                "piper",
                "--model", str(PIPER_MODEL_PATH),
                "--output_file", str(PIPER_OUTPUT_FILE)
            ],
            input=text,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        winsound.PlaySound(str(PIPER_OUTPUT_FILE), winsound.SND_FILENAME)

    finally:
        time.sleep(0.4)
        state.is_speaking = False


def speak(text: str):
    if not text:
        return

    threading.Thread(target=_speak_blocking, args=(text,), daemon=True).start()