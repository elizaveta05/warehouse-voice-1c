"""
hybrid_recognizer.py
--------------------
Гибридная схема: сначала пытаемся быстро распознать команду
через Vosk + grammar.  Если интент не распознан
(или grammar не подходит к тексту) → делаем «тяжёлое»
распознавание WhisperX, но только тогда.

Модуль не зависит от FastAPI, его удобно использовать
из асинхронных энд-поинтов.
"""

from __future__ import annotations
import json, pathlib, logging, wave
from typing import Optional
import logging
logger = logging.getLogger(__name__)

# ---------- Vosk ----------
from vosk import Model as VoskModel, KaldiRecognizer

_VOSK_PATH = pathlib.Path(r"C:\vosk\vosk-model-small-ru-0.22")

_GRAMMAR_PATH = pathlib.Path(__file__).with_suffix("") \
                 .parent / "grammar.json"

logging.info("Загружаем Vosk-модель из %s …", _VOSK_PATH)
_vosk_model = VoskModel(str(_VOSK_PATH))

with _GRAMMAR_PATH.open(encoding="utf-8") as f:
    _grammar = json.dumps(json.load(f))        # строка JSON для KaldiRecognizer


def _recognize_vosk(wav: pathlib.Path) -> str:
    """Быстрое CTC-распознавание Vosk. Возвращает 'text' ('' если пусто)."""
    with wave.open(str(wav), "rb") as wf:
        rec = KaldiRecognizer(_vosk_model, wf.getframerate(), _grammar)
        rec.SetWords(True)

        while True:
            data = wf.readframes(4000)
            if not data:
                break
            rec.AcceptWaveform(data)

        return json.loads(rec.FinalResult()).get("text", "")


# ---------- WhisperX (загружаем один раз) ----------
import whisperx

# Загружаем модель SMALL, квантованную в int8, на CPU
_wh_model = whisperx.load_model(
    "small",          # tiny | base | small | medium | large
    device="cpu",     # или 'cuda'
    compute_type="int8"
)

def _recognize_whisper(wav: pathlib.Path) -> str:
    """Более точное, но медленное распознавание."""
    result = _wh_model.transcribe(
        str(wav),
        language="ru"      
    )
    print("WhisperX output:", result)
    if "segments" in result:
        return " ".join([seg["text"] for seg in result["segments"]])
    return result.get("text", "")

# ---------- Public API ----------
from .nlu.intent_parser import parse as parse_intent


def transcribe_and_parse(wav_path: pathlib.Path) -> dict:
    text = _recognize_vosk(wav_path)
    intent_data = parse_intent(text)
    logger.debug("Parsed intent from Vosk: %s", intent_data)

    if intent_data["intent"] != "Unknown":
        return {"text": text, "engine": "vosk", **intent_data}

    logger.info("Vosk не распознал intent, падаем на WhisperX")
    text = _recognize_whisper(wav_path).strip().lower()
    intent_data = parse_intent(text)
    logger.debug("Parsed intent from WhisperX: %s", intent_data)
    return {"text": text, "engine": "whisper", **intent_data}