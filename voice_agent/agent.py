import queue
import sounddevice as sd
import wave
import os
import requests
import time
import io
import json
from vosk import Model, KaldiRecognizer
from faster_whisper import WhisperModel

# === НАСТРОЙКИ ===
SAMPLERATE = 16000
CHANNELS = 1
TRIGGER_PHRASE = "начать голосовое управление"
SERVER_URL = "http://localhost:8000"  

# === VOSK ===
vosk_model = Model(r"C:\vosk\vosk-model-small-ru-0.22")

vosk_recognizer = KaldiRecognizer(vosk_model, SAMPLERATE)

# === WHISPER ===
whisper = WhisperModel("small", device="cpu", compute_type="int8")

# === Очередь для потока аудио ===
q = queue.Queue()

def audio_callback(indata, frames, time_, status):
    if status:
        print("⚠️", status)
    q.put(bytes(indata))

def record_audio(duration_sec=4):
    """Собираем аудиофрагмент и возвращаем его как bytes в формате WAV"""
    audio_data = bytearray()
    target_bytes = SAMPLERATE * CHANNELS * 2 * duration_sec
    while len(audio_data) < target_bytes:
        audio_data.extend(q.get())

    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLERATE)
        wf.writeframes(audio_data)
    wav_io.seek(0)
    return wav_io.read()

def transcribe_whisper(wav_bytes):
    """Расшифровка через faster-whisper"""
    try:
        with io.BytesIO(wav_bytes) as wf:
            segments, _ = whisper.transcribe(wf, beam_size=1)
            return " ".join(seg.text for seg in segments).strip()
    except Exception as e:
        print("❌ Whisper error:", e)
        return ""

def send_to_server(text):
    try:
        print("🧠 Распознано:", text)
        resp = requests.post(f"{SERVER_URL}/recognize", files={
            "file": ("command.wav", io.BytesIO(text.encode()), "audio/wav")
        })
        if resp.ok:
            intent_data = resp.json()
            print("📤 Отправка в 1С:", intent_data)
            requests.post(f"{SERVER_URL}/command", json=intent_data)
        else:
            print("❌ Ошибка /recognize:", resp.status_code)
    except Exception as e:
        print("❌ Ошибка при отправке в 1С:", e)

def main():
    print("🎙 Агент запущен. Ожидание горячей фразы...")
    with sd.RawInputStream(samplerate=SAMPLERATE, blocksize=8000, dtype='int16',
                           channels=CHANNELS, callback=audio_callback):
        while True:
            data = q.get()
            if vosk_recognizer.AcceptWaveform(data):
                res = json.loads(vosk_recognizer.Result())
                text = res.get("text", "").lower()
                if TRIGGER_PHRASE in text:
                    print("🚀 Обнаружена горячая фраза:", text)
                    print("👂 Я вас слушаю...")
                    audio = record_audio(duration_sec=4)
                    result_text = transcribe_whisper(audio)
                    if result_text:
                        send_to_server(result_text)
                    else:
                        print("⚠️ Команда не распознана.")
                    print("↩️ Возврат в режим ожидания горячей фразы...")

if __name__ == "__main__":
    main()
