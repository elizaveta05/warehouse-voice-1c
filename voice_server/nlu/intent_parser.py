# server/nlu/intent_parser.py
from __future__ import annotations
import re
from typing import Dict
from ..metadata import MetadataMapper

# корни слов – только уникальная часть!
_STEMS = {
    "catalog": r"номенклатур|номенкатур|организац|сотрудник|должност|контрагент|адрес",
    "doc":     r"договор|приходн|расходн|накладн|перемещен|акт|заказ|расположен|инвент|инвентаризац|цен",
    "reg":     r"закупочн",
    "report":  r"актуальн|результат|остатк|остаток|хранени|продаж",
}

_mapper: MetadataMapper = MetadataMapper()

# ---------- вспомогательные фрагменты ----------
_TRIGGER  = r"(?:покажи|выведи|открой|открою|открыть)"
_CATALOG  = rf"(?P<catalog>(?:{_STEMS['catalog']})\w*)"
_DOC_SINGLE = rf"(?:{_STEMS['doc']})\w*"              # договор / накладн …
_DOC_PHRASE = rf"(?P<doc>{_DOC_SINGLE}(?:\s+\w+)*)"   # допускаем добавочные слова
_CATALOG_PHRASE = rf"(?P<catalog>{_STEMS['catalog']}\w*)"  
_REPORT   = rf"(?P<report>(?:{_STEMS['report']})\w*)"
_REG      = rf"(?P<reg>(?:{_STEMS['reg']})\w*)"
_OPT_CODE = r"(?:\s+код\s+(?P<code>\S+))?"
_OPT_NUM  = r"(?:\s+номер\s+(?P<number>\d+))?"
_REPORT_SINGLE = rf"(?:{_STEMS['report']})\w*"          # остатк / хранен / …
_REPORT_PHRASE = rf"(?P<report>{_REPORT_SINGLE}(?:\s+\w+)*)"
_REPORT_PREFIX = r"(?:отч[её]т(?:\s+\w+)*\s+)?"
_STEMS["reg"] = r"закупочн|цена|цен|список"   # дополнили
_REG_SINGLE = rf"(?:{_STEMS['reg']})\w*"              # закупочн / цена / …
_REG_PHRASE = rf"(?P<reg>{_REG_SINGLE}(?:\s+\w+)*)"   # ► допускаем дополнительные слова
_CREATE = r"(?:создай|создать|добавь|добавить|начать|начни|заключить)"


_PATTERNS = [
    # -------- Справочник: список / код / наименование --------
    (re.compile(rf"^{_TRIGGER}\s+(?:справочн\w*\s+)?{_CATALOG}{_OPT_CODE}$",
                re.I), "OpenCatalogList"),
    (re.compile(rf"^(?:открой|открыть)\s+(?:справочн\w*\s+)?{_CATALOG}\s+код\s+(?P<code>\S+)",
                re.I), "OpenCatalogByCode"),
    (re.compile(rf"^(?:открой|открыть)\s+(?:справочн\w*\s+)?{_CATALOG}\s+наименован\w*\s+(?P<name>.+)$",
                re.I), "OpenCatalogByName"),

    (re.compile(
        rf"^{_CREATE}\s+(?:нов(ый|ую|ого)\s+)?"     # «создай новую …»
        rf"{_CATALOG_PHRASE}$",
        re.I),"CreateCatalog"),

    # -------- Документы --------

    # 1. Открыть документ по номеру  
    (
        re.compile(
            rf"^{_TRIGGER}\s+{_DOC_PHRASE}"      
            rf"\s*(?:номер|№|#)?\s*"       
            rf"(?P<number>\d+)$",            
            re.I,
        ),
        "OpenDocumentByNumber",
    ),

    # 2. Список документов
    (
        re.compile(
            rf"^{_TRIGGER}\s+(?:список\s+)?"   
            rf"{_DOC_PHRASE}$",
            re.I,
        ),
        "OpenDocumentList",
    ),

    (re.compile(
        rf"^{_CREATE}\s+(?:нов(ый|ую|ое)\s+)?"     
        rf"{_DOC_PHRASE}$",
        re.I),
     "CreateDocument"),              


    # -------- Отчёты --------
    (
        re.compile(
        rf"^(?:запусти|{_TRIGGER})\s+"
        rf"{_REPORT_PREFIX}"       
        rf"{_REPORT_PHRASE}$",
        re.I),
        "RunReport",
    ),

    # -------- Регистры сведений --------
    (
        re.compile(
        rf"^{_TRIGGER}\s+"                       
        rf"(?:регистр(?:\s+сведений)?\s+)?"     
        rf"{_REG_PHRASE}$",                    
        re.I),
        "OpenInfoRegister",
    ),

    # -------- fallback --------
    (re.compile(r".+", re.I), "Unknown"),
]

def parse(text: str) -> Dict:
    text = text.strip().lower()
    for pattern, intent in _PATTERNS:
        m = pattern.search(text)
        if m:
            fields = {k: v for k, v in m.groupdict().items() if v}
            return {"intent": intent, "fields": fields}
    return {"intent": "Unknown", "fields": {}}

def parse_and_enrich(text: str) -> Dict:
    result = parse(text)
    result["fields"] = _mapper.enrich_fields(result["intent"], result["fields"])
    return result
