import json
import queue
import time
from threading import Event

import sounddevice as sd
from vosk import KaldiRecognizer, Model

import state
from config import MIC_BLOCK_SIZE, MIC_DEVICE, MIC_SAMPLE_RATE, VOSK_MODEL_PATH

model = Model(str(VOSK_MODEL_PATH))


def listen(
    timeout_seconds: float | None = None,
    *,
    stop_event: Event | None = None,
) -> str:
    """Listen for one recognized utterance.

    ``stop_event`` lets the unified FastAPI process stop the microphone worker
    without waiting for another spoken phrase. A separate audio queue is used
    per call so stale audio cannot leak between listening sessions.
    """
    state.set_status("listening")

    audio_queue: queue.Queue[bytes] = queue.Queue()
    recognizer = KaldiRecognizer(model, MIC_SAMPLE_RATE)
    started_at = time.monotonic()

    def callback(indata, frames, callback_time, status):
        del frames, callback_time
        if status:
            # PortAudio status messages are diagnostic only; audio can still be
            # usable, so do not terminate the listener here.
            pass
        audio_queue.put(bytes(indata))

    try:
        with sd.RawInputStream(
            samplerate=MIC_SAMPLE_RATE,
            blocksize=MIC_BLOCK_SIZE,
            dtype="int16",
            channels=1,
            device=MIC_DEVICE,
            callback=callback,
        ):
            while True:
                if stop_event and stop_event.is_set():
                    return ""

                if (
                    timeout_seconds is not None
                    and time.monotonic() - started_at >= timeout_seconds
                ):
                    return ""

                try:
                    data = audio_queue.get(timeout=0.25)
                except queue.Empty:
                    continue

                if state.is_speaking():
                    continue

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()

                    if text:
                        print("You:", text)

                    return text
    finally:
        if not (stop_event and stop_event.is_set()):
            state.set_status("idle")
