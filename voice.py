import queue
import sounddevice as sd
import json
from pathlib import Path
from vosk import Model, KaldiRecognizer
import state

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "vosk-model-small-en-us-0.15"

model = Model(str(MODEL_PATH))
q = queue.Queue()


def callback(indata, frames, time, status):
    q.put(bytes(indata))


def listen(timeout_seconds=None) -> str:
    samplerate = 48000
    rec = KaldiRecognizer(model, samplerate)

    with sd.RawInputStream(
        samplerate=samplerate,
        blocksize=8000,
        dtype="int16",
        channels=1,
        device=36,
        callback=callback
    ):
        while True:
            try:
                if timeout_seconds is None:
                    data = q.get()
                else:
                    data = q.get(timeout=timeout_seconds)
            except queue.Empty:
                return ""

            if state.is_speaking:
                continue

            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "").strip()
                if text:
                    print("You:", text)
                return text