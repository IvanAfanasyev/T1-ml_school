# Algorithm

Папка `algorithm/` содержит бизнес-логику CloudMatch.

```text
algorithm/
  cloudmatch/
    agent/       диалог, извлечение запроса, pipeline, форматирование ответа
    data/        загрузка нормализованных JSON
    geo/         нормализация регионов и fallback
    llm/         клиент LLM и prompt-шаблоны
    ranking/     фильтры, бюджет, entity match, итоговое ранжирование
    retrieval/   embeddings + BM25
    schemas/     Pydantic-модели данных
  scripts/       build_indexes, import_parser_data, демо и оценка качества
```

Обычный запрос:

```text
текст пользователя
  -> LLM extractor
  -> query validator
  -> retrieval
  -> ranking
  -> top-3 сервисов
```

Комплексный запрос:

```text
интернет-магазин: backend + PostgreSQL + S3 + backup + balancer
  -> разбор на компоненты
  -> отдельный поиск по каждому компоненту
  -> сборка связок от одного провайдера
  -> #1, #2, #3 связки сервисов
```

Почему связки собираются от одного провайдера:

- проще подключать компоненты внутри одного облака;
- меньше сетевых и организационных рисков;
- проще объяснить результат пользователю;
- экспертная проверка ожидает цельную инфраструктурную связку, а не случайную смесь провайдеров.

Важные команды:

```bash
python -m algorithm.scripts.build_indexes
python -m algorithm.scripts.run_search_demo_user
python -m algorithm.scripts.import_parser_data --source-dir "/path/to/parser/data"
```
