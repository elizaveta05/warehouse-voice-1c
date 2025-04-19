# Voice JSON Schema v0.1

| Intent        | Обязательные поля            | Пример JSON                                                                 |
|---------------|------------------------------|-----------------------------------------------------------------------------|
| CreateDocument| document, Контрагент, Склад  | {"intent":"CreateDocument","document":"Приход","Контрагент":"ООО Альфа","Склад":"Основной"} |
| AddPosition   | Номенклатура, Количество     | {"intent":"AddPosition","Номенклатура":"Монитор","Количество":5}            |
| ConductDocument| document_id                  | {"intent":"ConductDocument","document_id":"12345"}                          |
