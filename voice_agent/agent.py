"""
voice_agent/agent.py
Запускается из 1С.  Слушает триггер‑фразу («начать голосовое управление»),
записывает аудио команды в WAV 16 kHz mono и отправляет
на voice_server /recognize.  Работает независимо от GUI‑потоков 1С.
"""

import json, queue, threading, time, logging, wave, io, requests, os, sys, pathlib
from collections import deque
from contextlib import contextmanager

import pyaudio
from vosk import Model, KaldiRecognizer

BASE_DIR = pathlib.Path(__file__).resolve().parent
CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))

logging.basicConfig(
    filename=BASE_DIR / "agent.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

RATE = CONFIG["SAMPLERATE"]
CHANNELS = CONFIG["CHANNELS"]
BITS = CONFIG["BITS"]
DEVICE_INDEX = CONFIG["DEVICE_INDEX"]

TRIGGER_PHRASE = CONFIG["TRIGGER_PHRASE"].lower()
SERVER_URL = CONFIG["SERVER_URL"].rstrip("/")

SILENCE_MS = CONFIG["SILENCE_MS"]
SILENCE_THRESHOLD = CONFIG["SILENCE_THRESHOLD"]
MAX_RECORD_SEC = CONFIG["MAX_RECORD_SEC"]


@contextmanager
def open_audio_stream():
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=RATE // 10,
        input_device_index=DEVICE_INDEX,
    )
    try:
        yield stream
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


def rms(frame_bytes: bytes) -> int:
    """Root‑mean‑square of 16‑bit samples."""
    import numpy as np

    a = np.frombuffer(frame_bytes, dtype=np.int16)
    return int((a.astype(np.int32) ** 2).mean() ** 0.5)


def detect_hotword():
    """Горячая фраза через Vosk."""
    model_path = os.environ.get("VOSK_MODEL", str(BASE_DIR / "vosk-model-small-ru-0.22"))
    if not os.path.isdir(model_path):
        logging.error("Vosk model not found: %s", model_path)
        sys.exit(1)

    model = Model(model_path)
    rec = KaldiRecognizer(model, RATE)

    logging.info("Start listening…")
    with open_audio_stream() as stream:
        while True:
            data = stream.read(RATE // 10, exception_on_overflow=False)
            if rec.AcceptWaveform(data):
                text = json.loads(rec.Result())["text"]
                logging.debug("Partial phrase: %s", text)
                if TRIGGER_PHRASE in text.lower():
                    logging.info("Hotword detected")
                    record_and_send(stream)  # stream already open
                    rec.Reset()


def record_and_send(stream):
    """Записываем до тишины или MAX_RECORD_SEC, отправляем серверу."""
    frames = []
    silent_chunks = 0
    chunk_size = RATE // 10  # 100 ms
    max_chunks = int(MAX_RECORD_SEC * 10)

    for i in range(max_chunks):
        chunk = stream.read(chunk_size, exception_on_overflow=False)
        frames.append(chunk)
        if rms(chunk) < SILENCE_THRESHOLD:
            silent_chunks += 1
        else:
            silent_chunks = 0

        if silent_chunks * 100 >= SILENCE_MS and i > 5:
            break

    wav_bytes = io.BytesIO()
    with wave.open(wav_bytes, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(BITS // 8)
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    wav_bytes.seek(0)
    logging.info("Sending %d bytes to server", len(wav_bytes.getbuffer()))
    try:
        resp = requests.post(
            SERVER_URL + "/recognize",
            data=wav_bytes,
            headers={"Content-Type": "audio/wav"},
            timeout=30,
        )
        resp.raise_for_status()
        logging.info("Server response: %s", resp.text)
    except Exception as e:
        logging.exception("Failed to send audio: %s", e)


if __name__ == "__main__":
    try:
        detect_hotword()
    except KeyboardInterrupt:
        print("Exiting")
