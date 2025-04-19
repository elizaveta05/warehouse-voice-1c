from fastapi import FastAPI, UploadFile, File
from typing import Dict, Any

app = FastAPI(title="Warehouse Voice API")

@app.post("/recognize")
async def recognize(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Принимает аудиофайл (ogg, wav и т.п.), возвращает
    заглушку JSON с intent и fields.
    TODO: заменить stub на ASR+NLU.
    """
    # TODO: реализовать распознавание и разбор
    return {
        "intent": "ExitVoice",
        "fields": {}
    }
