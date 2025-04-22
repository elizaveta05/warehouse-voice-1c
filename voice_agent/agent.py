import time, json, requests, queue
import sounddevice as sd
import vosk
import sys

model = vosk.Model("models/vosk-model-ru")
recognizer = vosk.KaldiRecognizer(model, 16000)
q = queue.Queue()

config = {
    "hotword": "начать голосовое управление",
    "1c_endpoint": "http://localhost:8080/command",
    "sample_rate": 16000
}

def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

def main():
    print("Агент запущен, слушаем микрофон...")

    with sd.RawInputStream(samplerate=config["sample_rate"], blocksize=8000,
                           dtype="int16", channels=1, callback=callback):
        while True:
            data = q.get()
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").lower()
                if config["hotword"] in text:
                    print(f"[HOTWORD] → {text}")
                    try:
                        requests.post(config["1c_endpoint"], json={
                            "intent": "OpenArrivalList",
                            "fields": {}
                        })
                        print("→ Команда отправлена в 1С")
                    except Exception as e:
                        print("Ошибка отправки в 1С:", e)
                    time.sleep(1.5)
