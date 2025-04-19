# Voice JSON Schema v0.1

| Intent        | Обязательные поля            | Пример JSON                                                                 |
|---------------|------------------------------|-----------------------------------------------------------------------------|
| CreateDocument| document, Контрагент, Склад  | {"intent":"CreateDocument","document":"Приход","Контрагент":"ООО Альфа","Склад":"Основной"} |
| AddPosition   | Номенклатура, Количество     | {"intent":"AddPosition","Номенклатура":"Монитор","Количество":5}            |
| ConductDocument| document_id                  | {"intent":"ConductDocument","document_id":"12345"}                          |
# Voice JSON Schema v0.2

| Intent           | Обязательные поля                          | Пример JSON                                                                                          |
|------------------|--------------------------------------------|------------------------------------------------------------------------------------------------------|
| ExitVoice        | —                                          | {"intent":"ExitVoice"}                                                                               |
| CreateArrival    | —                                          | {"intent":"CreateArrival"}                                                                           |
| CreateShipment   | —                                          | {"intent":"CreateShipment"}                                                                          |
| AddPosition      | Номенклатура, Количество, ЦенаЗакупки?     | {"intent":"AddPosition","Номенклатура":"Телевизор LG","Количество":5,"ЦенаЗакупки":30000}             |
| ScanPosition     | штрихкод, Количество                       | {"intent":"ScanPosition","штрихкод":"B2","Количество":5}                                             |
| SetBase          | Основание                                  | {"intent":"SetBase","Основание":"Договор 123"}                                                       |
| SaveDocument     | —                                          | {"intent":"SaveDocument"}                                                                            |
| CreateTransfer   | —                                          | {"intent":"CreateTransfer"}                                                                          |
| CreateInventory  | —                                          | {"intent":"CreateInventory"}                                                                         |
| OpenArrivalList  | —                                          | {"intent":"OpenArrivalList"}                                                                         |
| OpenShipmentList | —                                          | {"intent":"OpenShipmentList"}                                                                        |
| CloseDocument    | —                                          | {"intent":"CloseDocument"}                                                                           |
| ShowStockReport  | date_from?, date_to?                       | {"intent":"ShowStockReport","date_from":"2025-05-01","date_to":"2025-05-10"}                           |
| ShowMovementReport | date_from, date_to                       | {"intent":"ShowMovementReport","date_from":"2025-05-01","date_to":"2025-05-10"}                       |
| Help             | —                                          | {"intent":"Help"}                                                                                   |
| AddCatalogItem     | Наименование, Артикул?, Штрихкод?, Единица?, ЦенаЗакупки? | {"intent":"AddCatalogItem","Наименование":"Монитор LG","Артикул":"LG123","Штрихкод":"1","Единица":"шт","ЦенаЗакупки":5} |
