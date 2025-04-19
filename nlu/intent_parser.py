import re
from typing import Dict, Any, Optional

def parse_intent(text: str) -> Dict[str, Any]:
    """
    Примитивный разбор текста на интент и слоты по регулярным выражениям.
    Возвращает словарь {"intent": str, "fields": {...}}.
    """
    txt = text.lower().strip()

    # 1) Выход из режима
    if re.search(r"\b(выход|выйди)\b.*\bголосового режима\b", txt):
        return {"intent": "ExitVoice", "fields": {}}

    # 2) Создание документов
    if "приходн" in txt:
        return {"intent": "CreateArrival", "fields": {}}
    if "расходн" in txt:
        return {"intent": "CreateShipment", "fields": {}}
    if "перемещ" in txt:
        return {"intent": "CreateTransfer", "fields": {}}
    if "инвентаризац" in txt:
        return {"intent": "CreateInventory", "fields": {}}

    # 3) Заполнение позиций
    m = re.search(r"добавь (позицию )?(?P<name>[\w\s]+?)(?:[, ]+количеств(?:о|е)\s*(?P<qty>\d+))", txt)
    if m:
        fields = {"Номенклатура": m.group("name").strip()}
        if m.group("qty"):
            fields["Количество"] = int(m.group("qty"))
        return {"intent": "AddPosition", "fields": fields}

    # 4) Сохранение
    if re.search(r"\b(сохрани|запиши)\b.*\bдокумент", txt):
        return {"intent": "SaveDocument", "fields": {}}

    # 5) Открытие списков
    if "список приходн" in txt:
        return {"intent": "OpenArrivalList", "fields": {}}
    if "список расходн" in txt:
        return {"intent": "OpenShipmentList", "fields": {}}

    # 6) Отчёты
    if "остатк" in txt:
        return {"intent": "ShowStockReport", "fields": {}}
    if "движени" in txt:
        return {"intent": "ShowMovementReport", "fields": {}}

    # 7) Помощь
    if "что я могу сказать" in txt or "помощ" in txt:
        return {"intent": "Help", "fields": {}}

    # По умолчанию
    return {"intent": "Unknown", "fields": {"text": text}}
