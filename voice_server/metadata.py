# server/metadata.py
from typing import Dict, List, Optional

class MetadataMapper:
    __STATIC_MAP: Dict[str, str] = {
        # справочники
        "номенклатур": "Номенклатура",
        "номенкатур": "Номенклатура",
        "организац":    "Организация",
        "сотрудник":    "Сотрудники",
        "должност":     "Должность",
        "контрагент":   "Контрагенты",
        "адрес":        "АдресаХранения",
        # документы
        "приходн":      "ПриходнаяНакладная",
        "расходн":      "РасходнаяНакладная",
        "договор":      "ДоговорыКонтрагентов",
        "перемещен":    "ПеремещениеТоваров",
        "акт":          "АктПриёмаМатериалов",
        "заказ":        "ЗаказПоставщику",
        "расположен":   "РасположениеТоваров",
        "инвентаризац": "Инвентаризация",
        "инвент": "Инвентаризация",
        "цена":         "ЦенаНаПродажу",
        # регистры
        "список команд": "СписокКомандССервера",
        "закупочн":      "ЗакупочныеЦены",
        "закупочные цены": "ЗакупочныеЦены", 
        # отчёты
        "актуальн":     "АктуальныйЦеныНоменклатур",
        "остатк":       "ОстаткиНоменклатуры",
        "остаток":       "ОстаткиНоменклатуры",
        "хранен":       "ХранениеНоменклатуры",
        "результат":    "РезультатыИнвентаризации",
        "продаж":       "ОтчетПоПродажам",
    }

    def __init__(self, dynamic_names: Optional[List[str]] = None) -> None:
        self.__map = self.__STATIC_MAP.copy()
        if dynamic_names:
            for name in dynamic_names:
                self.__map.setdefault(name.lower(), name)

    def normalize(self, raw: str) -> str:
        raw = raw.lower().strip()
        # ищем самый длинный ключ, который является префиксом raw
        candidates = [k for k in self.__map if raw.startswith(k)]
        if not candidates:
            return raw
        key = max(candidates, key=len)
        return self.__map[key]

    def enrich_fields(self, intent: str, fields: Dict) -> Dict:
        for f in ("catalog", "doc", "report", "reg"):
            if f in fields:
                fields[f] = self.normalize(fields[f])
        return fields
