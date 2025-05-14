# server/metadata.py
from typing import Dict, List, Optional


class MetadataMapper:
    """
    Преобразует 'сырое' имя (как его сказал пользователь)
    в точное имя объекта конфигурации 1С.
    """

    # --- статическая мапа ---
    __STATIC_MAP: Dict[str, str] = {
        # ---- Справочники ----
        "номенклатура": "Номенклатура",
        "организация": "Организация",
        "сотрудник": "Сотрудники",
        "должность": "Должность",
        "контрагент": "Контрагенты",
        "адрес хранения": "АдресаХранения",

        # ---- Документы ----
        "приходная накладная": "ПриходнаяНакладная",
        "расходная накладная": "РасходнаяНакладная",
        "договор контрагентов": "ДоговорыКонтрагентов",
        "перемещение товаров": "ПеремещениеТоваров",
        "акт приёма материалов": "АктПриёмаМатериалов",
        "заказ поставщику": "ЗаказПоставщику",
        "расположение товаров": "РасположениеТоваров",
        "инвентаризация": "Инвентаризация",
        "перемещение товара": "ПеремещениеТовара",
        "заказ покупателю": "ЗаказПокупателю",
        "цена на продажу": "ЦенаНаПродажу",

        # ---- Регистры сведений ----
        "список команд с сервера": "СписокКомандССервера",
        "закупочные цены": "ЗакупочныеЦены",
        "цена продажи": "ЦенаПродажи",

        # ---- Отчёты ----
        "актуальные цены номенклатур": "АктуальныйЦеныНоменклатур",
        "остатки номенклатуры": "ОстаткиНоменклатуры",
        "хранение номенклатуры": "ХранениеНоменклатуры",
        "результаты инвентаризации": "РезультатыИнвентаризации",
        "отчет по продажам": "ОтчетПоПродажам",
    }

    def __init__(self, dynamic_names: Optional[List[str]] = None) -> None:
        """
        :param dynamic_names: список строк, полученных из 1С по HTTP.
                              Они расширят / переопределят статическую мапу.
        """
        self.__map: Dict[str, str] = self.__STATIC_MAP.copy()
        if dynamic_names:
            for name in dynamic_names:
                self.__map.setdefault(name.lower(), name)

    # ---------- публичные методы ----------
    def normalize(self, raw_name: str) -> str:
        """Вернёт точное имя из конфигурации или исходную строку."""
        if raw_name is None:
            return raw_name
        return self.__map.get(raw_name.strip().lower(), raw_name.strip())

    def enrich_fields(self, intent: str, fields: Dict) -> Dict:
        """
        Пройдёт по fields в зависимости от intent
        и заменит 'человеческие' названия на точные.
        """
        if intent in {"OpenCatalogList", "OpenCatalogByCode",
                      "OpenCatalogByName", "CreateCatalog"}:
            if "catalog" in fields:
                fields["catalog"] = self.normalize(fields["catalog"])

        elif intent in {"OpenDocumentList", "OpenDocumentByNumber",
                        "CreateDocument"}:
            if "doc" in fields:
                fields["doc"] = self.normalize(fields["doc"])

        elif intent == "RunReport" and "report" in fields:
            fields["report"] = self.normalize(fields["report"])

        elif intent == "OpenInfoRegister" and "reg" in fields:
            fields["reg"] = self.normalize(fields["reg"])

        return fields
