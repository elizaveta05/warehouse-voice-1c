import re
from typing import Dict

_PATTERNS = [
    # приходная накладная
    (re.compile(r"создай приходн(ую|ая) накладн", re.I), "CreateArrival"),
    # расходная
    (re.compile(r"создай расходн(ую|ая) накладн", re.I), "CreateShipment"),
    # добавить товар
    (re.compile(r"добав(ь|ить) товар (?P<item>.+?) количество (?P<qty>\d+)", re.I), "AddPosition"),
    # провести документ
    (re.compile(r"проведи документ", re.I), "SaveDocument"),
]


def parse(text: str) -> Dict:
    for pattern, intent in _PATTERNS:
        m = pattern.search(text)
        if m:
            return {"intent": intent, "fields": m.groupdict()}
    return {"intent": "Unknown", "fields": {}}
