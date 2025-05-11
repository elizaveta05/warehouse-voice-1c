"""
hybrid_recognizer.py
--------------------
Гибридная схема: сначала пытаемся быстро распознать команду
через Vosk + grammar. Если интent не распознан
(или grammar не подходит к тексту) → делаем «тяжёлое»
распознавание WhisperX, но только тогда.

Модуль не зависит от FastAPI, его удобно использовать
из асинхронных энд-поинтов.
"""

from __future__ import annotations
import json
import logging
import pathlib
import wave
import re

from vosk import Model as VoskModel, KaldiRecognizer
import whisperx

from .nlu.intent_parser import parse as parse_intent

logger = logging.getLogger(__name__)

# ---------- Paths ----------
_VOSK_PATH = pathlib.Path(r"C:\vosk\vosk-model-small-ru-0.22")
_GRAMMAR_PATH = pathlib.Path(__file__).with_suffix("").parent / "grammar.json"

# ---------- Vosk Model ----------
logger.info("Loading Vosk model from %s …", _VOSK_PATH)
_vosk_model = VoskModel(str(_VOSK_PATH))

with _GRAMMAR_PATH.open(encoding="utf-8") as f:
    _grammar = json.dumps(json.load(f))

def _recognize_vosk(wav: pathlib.Path) -> str:
    """Быстрое CTC-распознавание Vosk. Возвращает очищенный текст."""
    with wave.open(str(wav), "rb") as wf:
        rec = KaldiRecognizer(_vosk_model, wf.getframerate(), _grammar)
        rec.SetWords(True)
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            rec.AcceptWaveform(data)
        result = json.loads(rec.FinalResult())
        raw = result.get("text", "")
    return clean_text(raw)

# ---------- WhisperX Model ----------
_MODEL_NAME = "medium"    # tiny | base | small | medium | large
_DEVICE     = "cpu"       # или 'cuda'
logger.info("Loading WhisperX model %s on %s (int8)…", _MODEL_NAME, _DEVICE)
_wh_model = whisperx.load_model(_MODEL_NAME, device=_DEVICE, compute_type="int8")

def _recognize_whisper(wav: pathlib.Path) -> str:
    """Более точное, но медленное распознавание через WhisperX."""
    result = _wh_model.transcribe(str(wav), language="ru")
    logger.debug("WhisperX output: %s", result)
    if "segments" in result:
        raw = " ".join(seg["text"] for seg in result["segments"])
    else:
        raw = result.get("text", "")
    return clean_text(raw)

# ---------- Text Cleaning ----------
def clean_text(text: str) -> str:
    """
    Убираем все знаки пунктуации (в т.ч. запятые, точки и т.д.),
    нормализуем пробелы и приводим к нижнему регистру.
    """
    # Удаляем всё, что не буква/цифра/пробел (включая пунктуацию)
    no_punct = re.sub(r'[^\w\sа-яА-ЯёЁ0-9]', '', text)
    # Сжимаем несколько пробелов в один, обрезаем по краям
    norm    = re.sub(r'\s+', ' ', no_punct).strip()
    return norm.lower()

# ---------- Public API ----------
def transcribe_and_parse(wav_path: pathlib.Path) -> dict:
    """
    Пытаемся сначала быстро распознать команду через Vosk+grammar.
    Если intent != "Unknown", возвращаем результат.
    Иначе — падаем на WhisperX.
    """
    # 1) Vosk
    text = _recognize_vosk(wav_path)
    intent_data = parse_intent(text)
    logger.debug("Parsed intent from Vosk: %s", intent_data)
    if intent_data.get("intent") != "Unknown":
        return {"text": text, "engine": "vosk", **intent_data}

    # 2) WhisperX
    logger.info("Vosk не распознал intent, падаем на WhisperX")
    text = _recognize_whisper(wav_path)
    intent_data = parse_intent(text)
    logger.debug("Parsed intent from WhisperX: %s", intent_data)
    return {"text": text, "engine": "whisper", **intent_data}
