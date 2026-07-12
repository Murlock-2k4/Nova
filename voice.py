import queue
import sounddevice as sd
import json
from vosk import Model, KaldiRecognizer
import state
from config import (
    VOSK_MODEL_PATH,
    MIC_DEVICE,
    MIC_SAMPLE_RATE,
    MIC_BLOCK_SIZE,
)

model = Model(str(VOSK_MODEL_PATH))
q = queue.Queue()


def callback(indata, frames, time, status):
    q.put(bytes(indata))


def listen(timeout_seconds=None) -> str:
    state.set_status("listening")

    samplerate = MIC_SAMPLE_RATE
    rec = KaldiRecognizer(model, samplerate)

    try:
        with sd.RawInputStream(
            samplerate=samplerate,
            blocksize=MIC_BLOCK_SIZE,
            dtype="int16",
            channels=1,
            device=MIC_DEVICE,
            callback=callback,
        ):
            while True:
                try:
                    if timeout_seconds is None:
                        data = q.get()
                    else:
                        data = q.get(timeout=timeout_seconds)

                except queue.Empty:
                    return ""

                if state.is_speaking():
                    continue

                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "").strip()

                    if text:
                        print("You:", text)

                    return text

    finally:
        state.set_status("idle")