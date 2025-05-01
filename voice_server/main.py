from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
import tempfile, subprocess, shutil, os, json, pathlib, logging
from collections import deque
import pythoncom
from win32com.client import Dispatch
from .config import settings
from .hybrid_recognizer import transcribe_and_parse

# Логирование
logging.basicConfig(
    filename="voice_server.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("warehouse_voice_server")

# FastAPI + CORS
app = FastAPI(title="Warehouse Voice Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origins],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Вспомогательные функции
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

# 1С через COM‑соединение
def send_to_1c(intent: str | None, fields: dict | None) -> None:
    """
    Вызывает экспортированную процедуру 1С 'ПолучениеКомандССервера.ЗаписатьКомандуВРегистр'
    напрямую через COMConnector.Call.
    """
    if not intent:
        logger.warning("send_to_1c: empty intent, skipping")
        return

    pythoncom.CoInitialize()
    try:
        # 1. Подключаемся к ИБ
        connector = Dispatch("V83.COMConnector")
        ib_path = r'File="C:\Users\elozo\OneDrive\Документы\InfoBase7"'
        session = connector.Connect(ib_path)

        # 2. Формируем JSON-параметр
        payload = json.dumps(fields or {}, ensure_ascii=False)

        # 3. Вызываем экспортированную процедуру:
        #    первый аргумент — полное имя 'Модуль.Процедура', далее её параметры
        session.COMConnection.ЗаписатьКомандуВРегистр(intent, payload)


        logger.info("✔ sent to 1С: intent=%s", intent)

    except Exception:
        logger.error("❌ send_to_1c failed", exc_info=True)
    finally:
        pythoncom.CoUninitialize()

# Эндпоинты

@app.get("/ping")
async def ping():
    return JSONResponse({"status": "ok"})

@app.post("/recognize")
async def recognize(request: Request, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
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

     # 3. асинхронно отправляем в 1С
    background_tasks.add_task(send_to_1c, result.get("intent"), result.get("fields", {}))

    # 4. и сразу возвращаем клиенту результат
    return JSONResponse(result)


