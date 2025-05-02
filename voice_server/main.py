from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
import tempfile, subprocess, shutil, os, json, pathlib, logging
from collections import deque
import pythoncom
from win32com.client import Dispatch
from win32com.client import gencache
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
# Очередь отложенных команд для 1С
pending_commands = deque()

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

# 1С через COM‑соединение с HTTP‑fallback
def send_to_1c(intent: str, fields: dict) -> None:
    pythoncom.CoInitialize()
    try:
        connector = Dispatch("V83.COMConnector")
        # Подключаемся к файловой базе
        ib_path = r'File="C:\Users\elozo\OneDrive\Документы\InfoBase7"'
        conn = connector.Connect(ib_path)

        # диагностика (выведет список всех ваших экспортных процедур):
        available = [m for m in dir(conn) if not m.startswith("_")]
        print("Экспортные процедуры в conn:", available)

        payload = json.dumps(fields or {}, ensure_ascii=False)

        print("Передаваемые данные в 1с через COM:", intent, payload)
        conn.COMConnection.WriteTheCommandToTheRegister(intent, payload)

        print("✔ Команда записана через COM")
    except Exception as e:
        print("❌ Не получилось через COM, береём в очередь:", e)
        pending_commands.append({"intent": intent, "fields": fields or {}})
    finally:
        pythoncom.CoUninitialize()

# Эндпоинты

@app.get("/ping")
async def ping():
    return JSONResponse({"status": "ok"})

@app.get("/intent")
async def get_intent():
    """
    1С фон может опрашивать этот метод раз в несколько секунд.
    Возвращает по одной команде из очереди или 204, если команд нет.
    """
    if pending_commands:
        cmd = pending_commands.popleft()
        logger.info("/intent: delivering pending command %s", cmd)
        return JSONResponse(cmd)
    else:
        return Response(status_code=204)

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

    # Асинхронно отправляем в 1С (COM или очередь для HTTP)
    background_tasks.add_task(send_to_1c, result.get("intent"), result.get("fields", {}))

    # Возвращаем результат клиенту сразу
    return JSONResponse(result)

