# server/hybrid_recognizer.py
from __future__ import annotations  # Поддержка аннотаций типов из будущих версий
import json  # Для работы с JSON (грамматика Vosk и результат WhisperX)
import logging  # Для логирования работы модуля
import pathlib  # Для удобной работы с путями файловой системы
import wave  # Для чтения WAV-файлов
import re  # Для очистки и нормализации текста

from vosk import Model as VoskModel, KaldiRecognizer  # Vosk для быстрого CTC-распознавания
import whisperx  # WhisperX для более точного, но медленного распознавания

from .nlu.intent_parser import parse as parse_intent  # Наш парсер интентов и полей из текста

# --- Настройка логирования --------------------------------
# Получаем логгер текущего модуля по его __name__
logger = logging.getLogger(__name__)
# Создаем обработчик для вывода логов в консоль (терминал)
console_handler = logging.StreamHandler()
# Уровень вывода логов в консоль
console_handler.setLevel(logging.DEBUG)
# Формат сообщения (время, уровень, имя логгера, сообщение)
console_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
console_handler.setFormatter(console_formatter)
# Добавляем консольный обработчик к логгеру
logger.addHandler(console_handler)
# -----------------------------------------------------------

# ---------- Пути к моделям и файлам ----------
# Путь к папке с моделью Vosk (модель ru small)
_VOSK_PATH = pathlib.Path(r"C:\vosk\vosk-model-small-ru-0.22")
# Путь к файлу grammar.json, в котором описаны правила грамматики для Vosk
_GRAMMAR_PATH = pathlib.Path(__file__).with_suffix("").parent / "grammar.json"

# ---------- Загрузка модели Vosk ----------
logger.info("Loading Vosk model from %s …", _VOSK_PATH)
# Создаем экземпляр модели Vosk
_vosk_model = VoskModel(str(_VOSK_PATH))
# Загружаем грамматику из JSON в строку для передачи KaldiRecognizer
with _GRAMMAR_PATH.open(encoding="utf-8") as f:
    _grammar = json.dumps(json.load(f))


def _recognize_vosk(wav: pathlib.Path) -> str:
    """Быстрое CTC-распознавание через Vosk с применением заданной grammar."""
    # Открываем WAV-файл для чтения
    with wave.open(str(wav), "rb") as wf:
        # Инициализируем распознаватель с моделью, частотой дискретизации и грамматикой
        rec = KaldiRecognizer(_vosk_model, wf.getframerate(), _grammar)
        rec.SetWords(True)  # Включаем возвращение слов и метаинформации
        # Считываем аудиопоток порциями
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            rec.AcceptWaveform(data)  # Передаем порцию аудио в распознаватель
        # Получаем финальный результат в виде JSON строки
        result = json.loads(rec.FinalResult())
        raw = result.get("text", "")  # Извлекаем текст
    # Очищаем и нормализуем текст перед возвратом
    return clean_text(raw)

# ---------- Загрузка и настройка WhisperX ----------
_MODEL_NAME = "medium"    # Название модели: tiny | base | small | medium | large
_DEVICE     = "cpu"       # Устройство: 'cpu' или 'cuda' для GPU
logger.info("Loading WhisperX model %s on %s (int8)…", _MODEL_NAME, _DEVICE)
# Загружаем модель WhisperX с низкой точностью int8 для экономии памяти
_wh_model = whisperx.load_model(_MODEL_NAME, device=_DEVICE, compute_type="int8")


def _recognize_whisper(wav: pathlib.Path) -> str:
    """Более точное, но медленное распознавание через WhisperX."""
    # Запускаем транскрипцию через WhisperX
    result = _wh_model.transcribe(str(wav), language="ru")
    logger.debug("WhisperX output: %s", result)  # Логируем подробности
    # Извлекаем текст из сегментов, если они есть
    if "segments" in result:
        raw = " ".join(seg["text"] for seg in result["segments"])
    else:
        raw = result.get("text", "")
    # Очищаем и нормализуем текст перед возвратом
    return clean_text(raw)

# ---------- Очистка и нормализация текста ----------
def clean_text(text: str) -> str:
    """
    Убираем пунктуацию и спецсимволы, нормализуем пробелы и приводим к нижнему регистру.
    """
    # Удаляем всё, что не буквы, цифры или пробел
    no_punct = re.sub(r'[^\w\sа-яА-ЯёЁ0-9]', '', text)
    # Сжимаем повторяющиеся пробелы
    norm    = re.sub(r'\s+', ' ', no_punct).strip()
    return norm.lower()

# ---------- Публичный API модуля ----------
def transcribe_and_parse(wav_path: pathlib.Path) -> dict:
    """
    Выполняет транскрипцию аудио и парсинг интента.
    1) Сначала Vosk+grammar — быстрый режим.
    2) Если интент неизвестен, переходит на WhisperX — точный режим.
    """
    # 1) Быстрое распознавание через Vosk
    text = _recognize_vosk(wav_path)
    # Первичный парсинг интента
    intent_data = parse_intent(text)
    logger.debug("Parsed intent from Vosk: %s", intent_data)
    # Если интент понятен, возвращаем результат сразу
    if intent_data.get("intent") != "Unknown":
        return {"text": text, "engine": "vosk", **intent_data}

    # 2) Переходим к медленному, но точному WhisperX
    logger.info("Vosk не распознал intent, используем WhisperX")
    text = _recognize_whisper(wav_path)
    intent_data = parse_intent(text)
    logger.debug("Parsed intent from WhisperX: %s", intent_data)
    return {"text": text, "engine": "whisper", **intent_data}