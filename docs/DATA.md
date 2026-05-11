# Данные

Проект работает с нормализованными JSON-файлами в `data/normalized/`.

```text
data/normalized/
  providers.json
  services.json
  service_pricing_items.json
  parse_log.json
  errors.json
```

`providers.json` хранит провайдеров.  
`services.json` хранит облачные сервисы, которые показываются в витрине и участвуют в ранжировании.  
`service_pricing_items.json` хранит тарифные позиции, связанные с сервисами через `service_id`.  
`parse_log.json` фиксирует источники и дату сбора.  
`errors.json` хранит ошибки нормализации, если они появились при импорте.

После замены данных нужно запустить:

```bash
python -m algorithm.scripts.build_indexes
```

Если пришли новые файлы от парсера, их можно импортировать командой:

```bash
python -m algorithm.scripts.import_parser_data --source-dir "/path/to/parser/data"
```

После импорта нужно снова перестроить индекс.
