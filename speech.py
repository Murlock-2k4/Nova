import threading
import subprocess
from pathlib import Path
import winsound
import time
import state

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "en_US-amy-medium.onnx"
OUTPUT_FILE = BASE_DIR / "nova_output.wav"


def _speak_blocking(text: str):
    state.is_speaking = True

    try:
        subprocess.run(
            [
                "piper",
                "--model", str(MODEL_PATH),
                "--output_file", str(OUTPUT_FILE)
            ],
            input=text,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        winsound.PlaySound(str(OUTPUT_FILE), winsound.SND_FILENAME)

    finally:
        time.sleep(0.4)
        state.is_speaking = False


def speak(text: str):
    if not text:
        return

    threading.Thread(target=_speak_blocking, args=(text,), daemon=True).start()