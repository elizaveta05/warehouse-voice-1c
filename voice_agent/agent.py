import json
import logging
import wave
import io
import requests
import os
import sys
import pathlib
import time
import signal
import sys
import winsound
from contextlib import contextmanager

import sounddevice as sd
from vosk import Model, KaldiRecognizer

BASE_DIR = pathlib.Path(__file__).resolve().parent
CONFIG   = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))

logging.basicConfig(
    filename=BASE_DIR / "agent.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

RATE              = CONFIG["SAMPLERATE"]
CHANNELS          = CONFIG["CHANNELS"]
BITS              = CONFIG["BITS"]               # <— добавили сюда
DEVICE_INDEX      = CONFIG["DEVICE_INDEX"]
TRIGGER_PHRASE    = CONFIG["TRIGGER_PHRASE"].lower()
SERVER_URL        = CONFIG["SERVER_URL"].rstrip("/")
SILENCE_MS        = CONFIG["SILENCE_MS"]
SILENCE_THRESHOLD = CONFIG["SILENCE_THRESHOLD"]
MAX_RECORD_SEC    = CONFIG["MAX_RECORD_SEC"]

def _on_shutdown(signum, frame):
    logging.info("Получен сигнал завершения (%s), выхожу.", signum)
    sys.exit(0)

# Перехватываем SIGINT/SIGTERM
signal.signal(signal.SIGINT,  _on_shutdown)
signal.signal(signal.SIGTERM, _on_shutdown)

def rms(frame_bytes: bytes) -> int:
    import numpy as np
    a = np.frombuffer(frame_bytes, dtype=np.int16)
    return int((a.astype(np.int32) ** 2).mean() ** 0.5)


@contextmanager
def open_audio_stream():
    """Открывает input-стрим через sounddevice, отдаёт CFFI-буфер."""
    stream = sd.RawInputStream(
        samplerate=RATE,
        blocksize=RATE // 10,  # 100 ms
        dtype='int16',
        channels=CHANNELS,
        device=DEVICE_INDEX
    )
    try:
        stream.start()
        yield stream
    finally:
        stream.stop()
        stream.close()


def detect_hotword():
    """Горячая фраза через Vosk + запись команд."""
    model_path = os.environ.get("VOSK_MODEL", r"C:\vosk\vosk-model-small-ru-0.22")
    if not os.path.isdir(model_path):
        logging.error("Vosk model not found: %s", model_path)
        sys.exit(1)

    model = Model(model_path)
    rec   = KaldiRecognizer(model, RATE)
    logging.info("Start listening for hotword…")

    with open_audio_stream() as stream:
        while True:
            raw_block, overflow = stream.read(RATE // 10)
            data = bytes(raw_block)
            if rec.AcceptWaveform(data):
                text = json.loads(rec.Result()).get("text", "")
            else:
                text = json.loads(rec.PartialResult()).get("partial", "")

            logging.debug("Heard: %s", text)
            if TRIGGER_PHRASE in text.lower():
                logging.info("Hotword detected")
                rec.Reset()
                time.sleep(0.3)
                winsound.Beep(1000, 200)
                record_and_send(stream)
                rec.Reset()


def record_and_send(stream):
    """Записываем до тишины или MAX_RECORD_SEC, отправляем на сервер."""
    frames = []
    silent_chunks = 0
    chunk_ms       = 100
    max_chunks     = int(MAX_RECORD_SEC * 1000 / chunk_ms)
    speech_started = False

    logging.info("🎙️  Начало записи голосовой команды")

    for i in range(max_chunks):
        raw_block, overflow = stream.read(RATE // 10)
        chunk = bytes(raw_block)
        level = rms(chunk)
        logging.debug(f"chunk {i:03d}: rms={level}")

        if level >= SILENCE_THRESHOLD:
            if not speech_started:
                logging.info(f"🗣  Обнаружена речь на фрейме {i}")
            speech_started = True
            silent_chunks = 0
        else:
            if speech_started:
                silent_chunks += 1

        frames.append(chunk)

        if speech_started and silent_chunks * chunk_ms >= SILENCE_MS:
            logging.info(f"🔇 Затишье {silent_chunks * chunk_ms} ms — останавливаем запись")
            break

    duration_sec = len(frames) * chunk_ms / 1000
    logging.info(f"✅ Запись завершена: фреймов={len(frames)}, длительность≈{duration_sec:.2f} s")

    # упаковываем WAV
    wav_bytes = io.BytesIO()
    with wave.open(wav_bytes, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(BITS // 8)     # теперь BITS определён
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
        wav_bytes.seek(0)

    files = {"file": ("command.wav", wav_bytes, "audio/wav")}
    try:
        resp = requests.post(f"{SERVER_URL}/recognize", files=files, timeout=30)
        resp.raise_for_status()
        logging.info("Server response: %s", resp.text)
    except Exception as e:
        logging.exception("Failed to send audio: %s", e)


if __name__ == "__main__":
    try:
        detect_hotword()
    except KeyboardInterrupt:
        logging.info("Agent stopped by user")
        sys.exit(0)
