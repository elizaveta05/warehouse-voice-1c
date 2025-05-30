import json  # Стандартный модуль для работы с JSON: загрузка config, парсинг ответов сервера
import logging  # Модуль для логирования событий работы агента
import wave  # Для упаковки записанных звуковых фреймов в WAV-файл
import io  # Для работы с байтовыми потоками (BytesIO)
import requests  # HTTP-клиент для отправки запросов на сервер распознавания
import os  # Работа с путями и переменными окружения
import sys  # Для завершения процесса через sys.exit()
import pathlib  # Удобный класс для работы с файловыми путями
import time  # Для пауз между этапами (time.sleep)
import signal  # Перехват сигналов ОС (SIGINT/SIGTERM)
import winsound  # Для Windows-звуков (Beep)
from contextlib import contextmanager  # Для реализации контекстного менеджера открытого микрофонного потока

import sounddevice as sd  # Модуль для работы со звуковыми потоками (микрофон)
from vosk import Model, KaldiRecognizer  # Vosk: оффлайн ASR-модель и распознаватель

# Загрузка настроек из config.json
BASE_DIR = pathlib.Path(__file__).resolve().parent  # Директория текущего скрипта
CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))  # Парсим JSON

# Настройка логирования в файл agent.log
logging.basicConfig(
    filename=BASE_DIR / "agent.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Основные константы из конфига
RATE              = CONFIG["SAMPLERATE"]         # Частота дискретизации
CHANNELS          = CONFIG["CHANNELS"]           # Количество каналов (моно/стерео)
BITS              = CONFIG["BITS"]               # Глубина семпла (в битах)
DEVICE_INDEX      = CONFIG["DEVICE_INDEX"]       # Индекс микрофонного устройства
TRIGGER_PHRASE    = CONFIG["TRIGGER_PHRASE"].lower()  # Горячая фраза для активации (в нижнем регистре)
SERVER_URL        = CONFIG["SERVER_URL"].rstrip("/")   # URL сервера распознавания, без завершающего слэша
SILENCE_MS        = CONFIG["SILENCE_MS"]         # Время тишины (ms) для окончания записи
SILENCE_THRESHOLD = CONFIG["SILENCE_THRESHOLD"]  # Порог RMS для определения речи/тишины
MAX_RECORD_SEC    = CONFIG["MAX_RECORD_SEC"]     # Максимальная длительность записи (секунд)

# Обработка завершения через Ctrl+C или kill
def _on_shutdown(signum, frame):
    logging.info("Получен сигнал завершения (%s), выхожу.", signum)
    sys.exit(0)

signal.signal(signal.SIGINT,  _on_shutdown)   # SIGINT (Ctrl+C)
signal.signal(signal.SIGTERM, _on_shutdown)   # SIGTERM (kill)

# Функция для оценки уровня громкости (RMS) в аудиофрейме
def rms(frame_bytes: bytes) -> int:
    import numpy as np
    a = np.frombuffer(frame_bytes, dtype=np.int16)       # Преобразуем байты в массив int16
    return int((a.astype(np.int32) ** 2).mean() ** 0.5)  # Вычисляем корень из среднего квадрата

# Контекстный менеджер для открытия/закрытия аудиопотока
@contextmanager
def open_audio_stream():
    """Открывает RawInputStream и гарантированно закрывает его."""
    stream = sd.RawInputStream(
        samplerate=RATE,
        blocksize=RATE // 10,  # читаем по 100 ms
        dtype='int16',
        channels=CHANNELS,
        device=DEVICE_INDEX
    )
    try:
        stream.start()  # запускаем поток
        yield stream    # возвращаем объект для чтения данных
    finally:
        stream.stop()   # останавливаем поток
        stream.close()  # закрываем ресурс

# Основная функция: детект «горячей фразы» и запуск записи команды
def detect_hotword():
    """Слушаем микрофон, ищем горячую фразу через Vosk, запускаем record_and_send."""
    model_path = os.environ.get("VOSK_MODEL", r"C:\vosk\vosk-model-small-ru-0.22")
    if not os.path.isdir(model_path):
        logging.error("Vosk model not found: %s", model_path)
        sys.exit(1)  # без модели работать бессмысленно

    model = Model(model_path)                     # загружаем модель Vosk
    rec   = KaldiRecognizer(model, RATE)          # создаём распознаватель
    logging.info("Start listening for hotword…")

    with open_audio_stream() as stream:
        while True:
            raw_block, overflow = stream.read(RATE // 10)  # читаем 100 ms
            data = bytes(raw_block)
            # Если Vosk вернул завершённый результат
            if rec.AcceptWaveform(data):
                text = json.loads(rec.Result()).get("text", "")
            else:
                text = json.loads(rec.PartialResult()).get("partial", "")

            logging.debug("Heard: %s", text)
            # Если в услышанном есть триггерная фраза
            if TRIGGER_PHRASE in text.lower():
                speak_async("Слушаю")  # озвучиваем начало записи
                logging.info("Hotword detected")
                rec.Reset()            # сбрасываем состояние распознавателя
                time.sleep(0.3)        # небольшая задержка перед записью
                winsound.Beep(1000, 200)  # короткий звуковой сигнал Windows
                record_and_send(stream)   # переходим к записи команды
                rec.Reset()            # сброс перед следующей активацией

# Функция записи звука и отправки на сервер распознавания
def record_and_send(stream):
    """Записываем в буфер до тишины или MAX_RECORD_SEC, отправляем WAV на сервер."""
    frames = []          # список байтов аудиофреймов
    silent_chunks = 0    # счётчик подряд идущих тихих фреймов
    chunk_ms       = 100 # длительность одного фрейма в ms
    max_chunks     = int(MAX_RECORD_SEC * 1000 / chunk_ms)
    speech_started = False

    speak_async("Принято")  # озвучиваем момент начала записи
    logging.info("🎙️  Начало записи голосовой команды")

    for i in range(max_chunks):
        raw_block, overflow = stream.read(RATE // 10)
        chunk = bytes(raw_block)
        level = rms(chunk)  # вычисляем уровень громкости
        logging.debug(f"chunk {i:03d}: rms={level}")

        if level >= SILENCE_THRESHOLD:
            if not speech_started:
                logging.info(f"🗣  Обнаружена речь на фрейме {i}")
            speech_started = True
            silent_chunks = 0
        else:
            if speech_started:
                silent_chunks += 1

        frames.append(chunk)

        # Если после начала речи накопилась достаточная «тишина»
        if speech_started and silent_chunks * chunk_ms >= SILENCE_MS:
            logging.info(f"🔇 Затишье {silent_chunks * chunk_ms} ms — останавливаем запись")
            break

    duration_sec = len(frames) * chunk_ms / 1000
    logging.info(f"✅ Запись завершена: фреймов={len(frames)}, длительность≈{duration_sec:.2f} s")

    # Упаковываем в WAV через BytesIO
    wav_bytes = io.BytesIO()
    with wave.open(wav_bytes, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(BITS // 8)
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
        wav_bytes.seek(0)  # возвращаем указатель в начало

    files = {"file": ("command.wav", wav_bytes, "audio/wav")}
    try:
        # Отправляем на FastAPI /recognize
        resp = requests.post(f"{SERVER_URL}/recognize", files=files, timeout=30)
        resp.raise_for_status()
        logging.info("Server response: %s", resp.text)
        speak_async("Готово")  # озвучиваем завершение обработки
    except Exception as e:
        logging.exception("Failed to send audio: %s", e)

# Функция для озвучки любых текстовых сообщений асинхронно
def speak_async(text):
    """Инициализирует pyttsx3 в отдельном потоке, чтобы не блокировать основной."""
    def run():
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    threading.Thread(target=run, daemon=True).start()

# Точка входа: запускаем детекцию горячего слова
if __name__ == "__main__":
    try:
        detect_hotword()
        speak_async("Голосовой агент запущен")

    except KeyboardInterrupt:
        logging.info("Agent stopped by user")
        sys.exit(0)
