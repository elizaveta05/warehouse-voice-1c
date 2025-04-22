import os
import json
import subprocess
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any

# ASR‑модель для команд
import whisperx
# Hotword‑детектор
from vosk import Model as VoskModel, KaldiRecognizer

# Ваш парсер интентов
from nlu.intent_parser import parse_intent

app = FastAPI(title="Warehouse Voice API")

# Загрузка моделей при старте
print("Loading Whisper‑medium model (CPU, float32)…")
whisper_model = whisperx.load_model("medium", device="cpu", compute_type="float32")

# print("Loading Vosk hotword model…")
# vosk_model = VoskModel("models/vosk-model-ru")  # путь к Vosk‑модели

class RecognizeResponse(BaseModel):
    intent: str
    fields: Dict[str, Any]

def save_tmp(file: UploadFile) -> str:
    """Сохраняет UploadFile во временную папку, возвращает путь"""
    temp_dir = os.path.join(os.getcwd(), "temp_audio")
    os.makedirs(temp_dir, exist_ok=True)
    in_path = os.path.join(temp_dir, file.filename)
    with open(in_path, "wb") as f:
        f.write(file.file.read())
    return in_path

def to_wav16(path: str) -> str:
    """Конвертирует файл в WAV 16 kHz mono, возвращает путь к .wav"""
    if path.lower().endswith(".wav"):
        return path
    wav_path = path + ".wav"
    subprocess.run(
        ["ffmpeg", "-i", path, "-ar", "16000", "-ac", "1", wav_path, "-y"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True
    )
    return wav_path

@app.get("/ping")
async def ping():
    return JSONResponse({"ok": True})

@app.post("/hotword")
async def hotword(file: UploadFile = File(...)):
    """
    Детектирует ключевую фразу «начать голосовое управление».
    Принимает 1–2 с аудио, возвращает {"ok": true/false}.
    """
    # 1) Сохраняем и конвертим
    in_path = save_tmp(file)
    wav = to_wav16(in_path)

    # 2) Инициализируем детектор
    rec = KaldiRecognizer(vosk_model, 16000)
    import wave
    wf = wave.open(wav, "rb")

    # 3) Читаем фреймы и проверяем
    while True:
        data = wf.readframes(4000)
        if not data:
            break
        if rec.AcceptWaveform(data):
            res = json.loads(rec.Result())
            text = res.get("text", "").lower()
            if "начать голосовое управление" in text:
                return JSONResponse({"ok": True})
    return JSONResponse({"ok": False})

@app.post("/recognize", response_model=RecognizeResponse)
async def recognize(file: UploadFile = File(...)):
    """
    Транскрипция полного аудио (3–5 с) и парсинг интента.
    Возвращает JSON { intent: ..., fields: {...} }.
    """
    # 1) Сохраняем и конвертим
    in_path = save_tmp(file)
    wav = to_wav16(in_path)

    # 2) ASR через WhisperX
    result = whisper_model.transcribe(wav)
    segments = result.get("segments", [])
    text = " ".join(seg["text"] for seg in segments).strip()
    if not text:
        raise HTTPException(status_code=400, detail="Не удалось распознать речь")

    # 3) NLU‑парсинг
    parsed = parse_intent(text)

    return RecognizeResponse(intent=parsed["intent"], fields=parsed["fields"])