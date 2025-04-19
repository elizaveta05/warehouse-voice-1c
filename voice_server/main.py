import os
import whisperx
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from nlu.intent_parser import parse_intent
import subprocess

app = FastAPI(title="Warehouse Voice API")

# Загружаем модель один раз при старте
print("Loading Whisper‑medium model (CPU, float32)…")
model = whisperx.load_model("medium", device="cpu", compute_type="float32")

class RecognizeResponse(BaseModel):
    intent: str
    fields: Dict[str, Any]

@app.post("/recognize", response_model=RecognizeResponse)
async def recognize(file: UploadFile = File(...)):
    """
    Принимает аудиофайл (ogg, wav и т.п.), возвращает JSON:
    {
      "intent": "...",
      "fields": { ... }
    }
    """
    # 1) Сохраняем временный файл
    temp_dir = os.path.join(os.getcwd(), "temp_audio")
    os.makedirs(temp_dir, exist_ok=True)
    in_path = os.path.join(temp_dir, file.filename)
    with open(in_path, "wb") as f:
        f.write(await file.read())

    # 2) Если не WAV, конвертируем через ffmpeg
    if not in_path.lower().endswith(".wav"):
        wav_path = in_path + ".wav"
        cmd = ["ffmpeg", "-i", in_path, "-ar", "16000", "-ac", "1", wav_path, "-y"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    else:
        wav_path = in_path

    # 3) ASR: транскрибируем
    result = model.transcribe(wav_path)
    segments = result.get("segments", [])
    text = " ".join([seg["text"] for seg in segments]).strip()
    if not text:
        raise HTTPException(status_code=400, detail="Could not transcribe audio")

    # 4) NLU: парсим текст
    parsed = parse_intent(text)

    # 5) Возвращаем JSON
    return RecognizeResponse(intent=parsed["intent"], fields=parsed["fields"])
