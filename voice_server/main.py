from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
import tempfile, subprocess, shutil, os, json, pathlib, logging
from collections import deque

from .config import settings
from .hybrid_recognizer import transcribe_and_parse

# Настройка логирования серверных операций
logging.basicConfig(
    filename="voice_server.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("warehouse_voice_server")

app = FastAPI(title="Warehouse Voice Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origins],
    allow_methods=["*"],
    allow_headers=["*"],
)

# очередь для распознанных команд
_queue: deque[dict] = deque()

def save_tmp(upload: UploadFile) -> pathlib.Path:
    suffix = pathlib.Path(upload.filename or "audio").suffix or ".bin"
    tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="voice_", dir=settings.tmp_dir))
    raw_path = tmp_dir / f"in{suffix}"
    logger.debug("save_tmp: writing raw upload to %s", raw_path)
    with raw_path.open("wb") as f:
        shutil.copyfileobj(upload.file, f)

    if suffix.lower() != ".wav":
        wav_path = raw_path.with_suffix(".wav")
        cmd = [
            "ffmpeg", "-y", "-i", str(raw_path),
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(wav_path)
        ]
        logger.debug("save_tmp: converting via ffmpeg: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            logger.error("ffmpeg stderr: %s", result.stderr.decode(errors="ignore"))
            raise HTTPException(400, f"FFmpeg error: {result.stderr.decode()}")
        return wav_path

    return raw_path

@app.get("/ping")
async def ping():
    return JSONResponse({"status": "ok"})

@app.post("/recognize")
async def recognize(request: Request, file: UploadFile = File(...)):
    client = request.client.host
    logger.info("🟢 /recognize from %s: filename=%s", client, file.filename)
    try:
        path = save_tmp(file)
        logger.info("Uploaded file saved to %s", path)
    except Exception as e:
        logger.error("save_tmp failed", exc_info=True)
        raise HTTPException(400, f"Cannot save file: {e}")

    try:
        result = transcribe_and_parse(path)
        logger.info("transcribe_and_parse result: %s", result)
    except Exception as e:
        logger.error("transcribe_and_parse failed", exc_info=True)
        raise HTTPException(500, f"Recognition error: {e}")

    # 3) положить в очередь для 1С
    #    1С ждёт поля Intent и Fields
    _queue.append({
        "intent": result.get("intent"),
        "fields": result.get("fields", {}),
    })
    logger.info("   ➕ queued intent `%s`", result.get("intent"))

    # 4) вернуть ответ сразу
    logger.info("   ✅ returning JSON to client: %s", json.dumps(result, ensure_ascii=False))
    return JSONResponse(result)

@app.get("/intent")
async def get_intent():
    """
    1С опрашивает этот эндпоинт:
     - если есть команда — отдать её и удалить из очереди (200 + JSON)
     - иначе — вернуть 204 No Content без тела
    """
    if not _queue:
        return Response(status_code=204)
    cmd = _queue.popleft()
    logger.info("🟢 /intent -> %s", cmd)
    return JSONResponse({
        "Intent": cmd["intent"],
        "Fields": cmd["fields"],
    })