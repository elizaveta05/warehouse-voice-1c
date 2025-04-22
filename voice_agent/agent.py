import sounddevice as sd
import queue
import threading
import requests
import time
import io
import wave

SAMPLERATE = 16000
CHANNELS   = 1
CHUNK_SEC  = 3
SERVER_URL = "http://192.168.0.129:8000"  # или 192.168.0.129

audio_q = queue.Queue()

def audio_callback(indata, frames, time_info, status):
    if status:
        print("⚠ Audio status:", status)
    audio_q.put(bytes(indata))

def record_chunk(duration=3) -> bytes:
    """Накопление аудио на duration секунд, возвращает WAV в bytes."""
    frames = bytearray()
    target_size = SAMPLERATE * CHANNELS * 2 * duration
    while len(frames) < target_size:
        frames.extend(audio_q.get())

    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLERATE)
        wf.writeframes(frames)
    wav_io.seek(0)
    return wav_io.read()

def recognize_audio(audio_data: bytes) -> str:
    """Отправляет аудио на /recognize и возвращает intent или текст"""
    try:
        files = {"file": ("audio.wav", audio_data, "audio/wav")}
        resp = requests.post(f"{SERVER_URL}/recognize", files=files, timeout=15)
        if resp.ok:
            result = resp.json()
            print("🧠 Распознано:", result)
            return result
        else:
            print("❌ Ошибка /recognize:", resp.status_code)
    except Exception as e:
        print("❌ Исключение при /recognize:", e)
    return None

def main():
    print("🎙 Агент запущен. Ожидаю фразу 'начать голосовое управление'...")
    with sd.RawInputStream(samplerate=SAMPLERATE, blocksize=SAMPLERATE // 2, dtype='int16',
                           channels=CHANNELS, callback=audio_callback):

        while True:
            # 🔁 1. Ждём горячую фразу
            chunk = record_chunk(CHUNK_SEC)
            result = recognize_audio(chunk)
            if not result: continue

            text = result.get("fields", {}).get("text", "").lower()
            if "начать голосовое управление" not in text:
                print("🔇 Не горячая фраза:", text)
                continue

            print("🚀 Горячая фраза активировала режим команд")
            print("👂 Я вас слушаю")

            # 🔁 2. Переход в режим распознавания команды
            chunk = record_chunk(4)
            result = recognize_audio(chunk)
            if not result: continue

            # Отправка команды на /command
            try:
                requests.post(f"{SERVER_URL}/command", json=result, timeout=10)
                print("📤 Команда отправлена:", result.get("intent"))
            except Exception as e:
                print("❌ Ошибка /command:", e)

            print("⏳ Возврат в режим ожидания фразы...")
            time.sleep(1)

if __name__ == "__main__":
    main()
