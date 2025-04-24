from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
import tempfile, subprocess, uuid, shutil, os, json, pathlib, logging

from .config import settings
from .hybrid_recognizer import transcribe_and_parse


app = FastAPI(title="Warehouse Voice Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origins],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

try:
    import whisperx
    model = whisperx.load_model(
        settings.voicemodel,          # 'small'
        device=settings.device,       # 'cpu'
        compute_type="int8"           # ← безопасно для CPU
    )
except Exception as e:
    logging.error("Cannot load whisperx model: %s", e)
    model = None


def save_tmp(upload: UploadFile) -> pathlib.Path:
    suffix = pathlib.Path(upload.filename or "audio").suffix or ".bin"
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="voice_", dir=settings.tmp_dir)) / f"in{suffix}"
    with tmp.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    tmp_final = tmp
    # Convert to 16k WAV if needed
    if suffix.lower() != ".wav":
        wav_path = tmp.with_suffix(".wav")
        cmd = ["ffmpeg", "-y", "-i", str(tmp), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav_path)]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise HTTPException(400, f"FFmpeg error: {result.stderr.decode()}")
        tmp_final = wav_path
    return tmp_final


@app.post("/recognize")
async def recognize(file: UploadFile = File(...)):
    """
    Получаем WAV (16 kHz mono). Быстрая попытка Vosk + fallback WhisperX.
    Отдаём JSON, готовый для 1С.
    """
    path = save_tmp(file)                # как и раньше: сохраняем/конвертируем

    result = transcribe_and_parse(path)  # <-- новая функция
    logging.info("Engine=%s | Text='%s'", result["engine"], result["text"])

    return JSONResponse(result)
