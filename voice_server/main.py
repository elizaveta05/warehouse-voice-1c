# server/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Response, BackgroundTasks  # FastAPI для создания сервера, UploadFile и File для получения файлов, HTTPException для ошибок, Request и Response для обработки запросов, BackgroundTasks для фоновых задач
from fastapi.middleware.cors import CORSMiddleware  # Middleware для управления CORS
from starlette.responses import JSONResponse  # Удобный ответ с JSON
from collections import deque  # Двусторонняя очередь для отложенных команд
import tempfile  # Для создания временных директорий
import subprocess  # Для вызова внешних процессов (ffmpeg)
import shutil  # Для копирования файлов
import os  # Для работы с ОС (при необходимости)
import json  # Для сериализации полей команд в JSON
import pathlib  # Удобная работа с путями
import logging  # Логирование событий приложения
import pythoncom  # Для инициализации COM в потоке
from win32com.client import Dispatch  # Для взаимодействия с COM-объектами 1С
from .config import settings  # Конфигурация приложения (пути, CORS и т.д.)
from .hybrid_recognizer import transcribe_and_parse  # Модуль для распознавания и парсинга команд

# --- Настройка логирования --------------------------------
# Конфигурация базового логирования: пишет в файл voice_server.log
logging.basicConfig(
    filename="voice_server.log",  # Имя файла для логов
    level=logging.DEBUG,  # Минимальный уровень логирования (DEBUG и выше)
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Получаем именованный логгер для нашего приложения
logger = logging.getLogger("warehouse_voice_server")
# Добавляем обработчик для вывода логов также в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)  # Консоль выводит всё от DEBUG и выше
console_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)
# -----------------------------------------------------------

# --- Инициализация FastAPI и CORS ---
app = FastAPI(title="Warehouse Voice Server")  # Создаем приложение FastAPI
# Разрешаем CORS для указанных источников из настроек
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origins],  # Список разрешенных origin
    allow_methods=["*"],  # Разрешаем все HTTP-методы
    allow_headers=["*"],  # Разрешаем все заголовки
)

# --- Глобальные структуры данных ---
# Очередь для хранения команд, не отправленных в 1С из-за ошибок
pending_commands = deque()

# --- Вспомогательные функции ---
def save_tmp(upload: UploadFile) -> pathlib.Path:
    """
    Сохраняет загруженный файл во временную папку и конвертирует его в WAV 16 kHz моно через ffmpeg, если это нужно.
    :param upload: загруженный файл от клиента
    :return: путь к сохраненному *.wav или исходному файлу
    """
    # Определяем расширение файла или .bin по умолчанию
    suffix = pathlib.Path(upload.filename or "audio").suffix or ".bin"
    # Создаем уникальную временную папку внутри настроенной директории
    tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="voice_", dir=settings.tmp_dir))
    raw_path = tmp_dir / f"in{suffix}"  # Полный путь для исходного файла
    logger.debug("save_tmp: writing raw upload to %s", raw_path)
    # Копируем содержимое загруженного файла во временный файл
    with raw_path.open("wb") as f:
        shutil.copyfileobj(upload.file, f)

    # Проверяем, нужно ли конвертировать в WAV
    if suffix.lower() != ".wav":
        wav_path = raw_path.with_suffix(".wav")
        # Формируем команду ffmpeg для конвертации аудио
        cmd = [
            "ffmpeg", "-y",  # перезаписывать без запроса
            "-i", str(raw_path),  # входной файл
            "-ar", "16000",  # частота дискретизации 16 kHz
            "-ac", "1",  # моно канал
            "-c:a", "pcm_s16le",  # PCM 16-bit
            str(wav_path)
        ]
        logger.debug("save_tmp: converting via ffmpeg: %s", " ".join(cmd))
        # Запускаем ffmpeg и ждем завершения
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            # Если конвертация провалилась, логируем stderr и возвращаем ошибку клиенту
            logger.error("ffmpeg stderr: %s", result.stderr.decode(errors="ignore"))
            raise HTTPException(400, f"FFmpeg error: {result.stderr.decode()}")
        return wav_path

    # Если файл уже *.wav, возвращаем его путь без изменений
    return raw_path


def send_to_1c(intent: str, fields: dict) -> None:
    """
    Отправляет команду и поля в 1С через COM интерфейс.
    При неудаче сохраняет команду в очередь pending_commands для повторной попытки.
    :param intent: имя интента (действия)
    :param fields: словарь параметров для интента
    """
    # COM нужно инициализировать в каждом потоке
    pythoncom.CoInitialize()
    try:
        # Подключаемся к COMConnector 1С по пути к информационной базе
        connector = Dispatch("V83.COMConnector")
        ib_path = r'File="C:\Users\elozo\OneDrive\Документы\InfoBase7"'
        conn = connector.Connect(ib_path)

        # Опционально: логируем доступные методы COM-соединения
        available = [m for m in dir(conn) if not m.startswith("_")]
        logger.debug("Экспортные процедуры в conn: %s", available)

        # Сериализуем поля в JSON (с сохранением русских символов)
        payload = json.dumps(fields or {}, ensure_ascii=False)
        logger.debug("Передаваемые данные в 1С через COM: intent=%s, fields=%s", intent, payload)

        # Вызываем метод 1С для записи команды в регистр
        conn.COMConnection.WriteTheCommandToTheRegister(intent, payload)
        logger.info("✔ Команда успешно записана через COM")
    except Exception as e:
        # При ошибке логируем и сохраняем команду в очередь на повтор
        logger.error("❌ Ошибка отправки в 1С через COM: %s — добавляю в очередь", e)
        pending_commands.append({"intent": intent, "fields": fields or {}})
    finally:
        # Всегда деинициализируем COM
        pythoncom.CoUninitialize()

# --- HTTP-эндпоинты FastAPI ---
@app.get("/ping")
async def ping():
    """
    Проверочный эндпоинт: возвращает статус 'ok'.
    """
    return JSONResponse({"status": "ok"})

@app.get("/intent")
async def get_intent():
    """
    Эндпоинт для фонового опроса 1С.
    Возвращает одну отложенную команду или 204, если очередь пуста.
    """
    if pending_commands:
        cmd = pending_commands.popleft()  # Забираем первую команду из очереди
        logger.info("/intent: delivering pending command %s", cmd)
        return JSONResponse(cmd)
    # Если команд нет, отдаем 204 No Content
    return Response(status_code=204)

@app.post("/recognize")
async def recognize(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Основной эндпоинт: принимает аудио-файл, распознает команду и возвращает результат.
    Одновременно ставит отправку в 1С в фоновую задачу.
    """
    # IP клиента для логирования
    client = request.client.host
    logger.info("🟢 /recognize from %s: filename=%s", client, file.filename)

    # 1) Сохраняем и конвертируем файл
    try:
        path = save_tmp(file)
        logger.debug("Uploaded file saved to %s", path)
    except Exception as e:
        logger.exception("save_tmp failed")
        # Выбрасываем ошибку 400, если не удалось сохранить/конвертировать
        raise HTTPException(400, f"Cannot save file: {e}")

    # 2) Распознаем и парсим команду
    try:
        result = transcribe_and_parse(path)  # Возвращает словарь с text, engine, intent и fields
        logger.info("transcribe_and_parse result: %s", result)
    except Exception as e:
        logger.exception("transcribe_and_parse failed")
        # Ошибка распознавания -> 500 Internal Server Error
        raise HTTPException(500, f"Recognition error: {e}")

    # 3) Запускаем отправку команды в 1С в фоне, чтобы не тормозить ответ
    background_tasks.add_task(send_to_1c, result.get("intent"), result.get("fields", {}))

    # 4) Возвращаем результат клиенту сразу
    return JSONResponse(result)
