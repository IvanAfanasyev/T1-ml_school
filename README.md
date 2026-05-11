# CloudMatch

CloudMatch - MVP-сервис для подбора российских облачных сервисов по пользовательскому запросу. Пользователь пишет задачу обычным языком, система уточняет недостающие параметры, ищет подходящие сервисы в нормализованном каталоге и возвращает либо top-3 отдельных сервиса, либо несколько инфраструктурных связок.

Пример обычного запроса:

```text
база данных MySQL, москва, любой бюджет
```

Пример комплексного запроса:

```text
Нужен backend на Python с PostgreSQL, хранение изображений товаров,
backup базы данных и балансировщик для масштабирования.
```

## Полная структура проекта

```text
.
├── README.md
├── .env.example
├── .gitignore
├── .dockerignore
├── docker-compose.yml
├── backend/
│   ├── README.md
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── __init__.py
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       └── api/
│           ├── __init__.py
│           ├── chat.py
│           └── search.py
├── frontend/
│   ├── README.md
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── algorithm/
│   ├── README.md
│   ├── __init__.py
│   ├── cloudmatch/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── agent/
│   │   │   ├── dialog.py
│   │   │   ├── explainer.py
│   │   │   ├── explanation_builder.py
│   │   │   ├── pipeline.py
│   │   │   ├── query_extractor.py
│   │   │   ├── query_validator.py
│   │   │   └── user_response_formatter.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── constants.py
│   │   │   ├── hf_quiet.py
│   │   │   └── logging.py
│   │   ├── data/
│   │   │   ├── catalog.py
│   │   │   ├── loaders.py
│   │   │   ├── pricing_repository.py
│   │   │   ├── repositories.py
│   │   │   └── service_text.py
│   │   ├── evaluation/
│   │   │   ├── golden_dataset.py
│   │   │   ├── llm_judge.py
│   │   │   └── metrics.py
│   │   ├── geo/
│   │   │   └── region_resolver.py
│   │   ├── llm/
│   │   │   ├── client.py
│   │   │   └── prompts/
│   │   │       ├── explanation.py
│   │   │       ├── judge.py
│   │   │       └── query_extractor.py
│   │   ├── ranking/
│   │   │   ├── budget_matcher.py
│   │   │   ├── compliance_filter.py
│   │   │   ├── entity_matcher.py
│   │   │   ├── pricing_matcher.py
│   │   │   ├── scoring.py
│   │   │   └── topk.py
│   │   ├── retrieval/
│   │   │   ├── bm25.py
│   │   │   ├── embeddings.py
│   │   │   ├── hybrid.py
│   │   │   └── vector_store.py
│   │   └── schemas/
│   │       ├── evaluation.py
│   │       ├── pricing.py
│   │       ├── provider.py
│   │       ├── query.py
│   │       ├── ranking.py
│   │       └── service.py
│   └── scripts/
│       ├── build_indexes.py
│       ├── evaluate_ranking.py
│       ├── evaluate_with_judge.py
│       ├── generate_golden_dataset.py
│       ├── import_parser_data.py
│       ├── run_search_demo.py
│       └── run_search_demo_user.py
├── data/
│   ├── normalized/
│   │   ├── providers.json
│   │   ├── services.json
│   │   ├── service_pricing_items.json
│   │   ├── parse_log.json
│   │   └── errors.json
│   └── evaluation/
│       └── golden_dataset.json
├── docs/
│   ├── DATA.md
│   ├── DEPLOYMENT.md
│   └── TESTING.md
└── tests/
    ├── test_api_search.py
    ├── test_dialog_manager.py
    ├── test_metrics.py
    ├── test_normalized_data_structure.py
    ├── test_query_extractor.py
    ├── test_query_validator.py
    ├── test_region_resolver.py
    ├── test_scoring.py
    └── test_solution_bundle.py
```

## За что отвечает каждая часть

`backend/` - серверная часть. Здесь находится FastAPI-приложение, API-маршруты, Pydantic-модели входящих и исходящих данных, Dockerfile и список Python-зависимостей. Backend принимает запросы от сайта, вызывает алгоритм и возвращает frontend готовый JSON.

`frontend/` - интерфейс сайта. Здесь лежит статическая страница с витриной сервисов, диалоговым агентом и страницей о проекте. Frontend хранит историю чата в `localStorage` браузера и общается с backend через HTTP.

`algorithm/` - основная логика подбора. Здесь находится извлечение структуры запроса через LLM, диалоговые уточнения, поиск по embeddings и BM25, ранжирование, фильтры, работа с регионами, бюджетом, тарифами и форматирование ответа.

`data/normalized/` - нормализованные данные каталога. Это рабочий источник данных для MVP: провайдеры, сервисы, тарифные позиции и лог парсинга.

`data/evaluation/` - данные для проверки качества ранжирования. Сейчас там хранится golden dataset.

`docs/` - прикладная документация: данные, тестирование и деплой.

`tests/` - автоматические тесты. Они проверяют API, диалог, извлечение запроса, структуру данных, ranking и комплексные связки сервисов.

`docker-compose.yml` - запуск backend-контейнера.

`.env.example` - пример переменных окружения для LLM.

## Как устроен поток запроса

```text
Пользователь
  -> frontend/app.js
  -> POST /api/chat или POST /api/search
  -> backend/app/api/
  -> algorithm/cloudmatch/agent/
  -> data/normalized/
  -> ranking/retrieval
  -> backend response
  -> frontend rendering
```

В обычном запросе система возвращает top-3 отдельных сервиса. В комплексном запросе система сначала выделяет роли, например backend, database, storage, backup и balancer, затем подбирает связки сервисов. Каждая связка собирается от одного провайдера, чтобы компоненты было проще использовать вместе.

## Быстрый запуск локально

1. Создать виртуальное окружение:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Установить зависимости:

```bash
pip install -r backend/requirements.txt
```

3. Создать `.env`:

```bash
cp .env.example .env
```

В `.env` нужно указать ключ, base URL и модель LLM.

4. Построить embedding-индекс:

```bash
python -m algorithm.scripts.build_indexes
```

5. Запустить backend:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

6. Открыть API:

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

7. Открыть frontend:

Можно открыть `frontend/index.html` в браузере. При локальном открытии сайт обращается к `http://127.0.0.1:8000`. На сервере frontend обращается к тому же домену через `/api/...`.

## API

Основные endpoint:

- `GET /health` - проверка состояния backend.
- `POST /api/chat` - диалоговый агент.
- `POST /api/search` - прямой поиск по запросу.
- `GET /api/catalog/search` - список сервисов для витрины.
- `GET /api/catalog/services/{service_id}` - подробная карточка сервиса.

Пример запроса в чат:

```json
{
  "user_id": "local-user",
  "chat_id": "demo-chat",
  "message": "база данных MySQL, москва, любой бюджет",
  "with_explanation": true,
  "include_debug": false
}
```

## Данные

Рабочие файлы лежат в `data/normalized/`:

- `providers.json` - провайдеры;
- `services.json` - облачные сервисы;
- `service_pricing_items.json` - тарифные позиции;
- `parse_log.json` - источники и дата сбора;
- `errors.json` - ошибки импорта или нормализации.

После обновления JSON нужно перестроить индекс:

```bash
python -m algorithm.scripts.build_indexes
```

## Docker

Backend собирается из `backend/Dockerfile`. При сборке контейнера зависимости устанавливаются внутрь образа, затем копируются `backend/`, `algorithm/` и `data/normalized/`, после чего строится embedding-индекс.

Запуск:

```bash
docker compose up -d --build
docker compose logs -f backend
```

Frontend в production отдается Nginx как статические файлы. Запросы `/api`, `/health`, `/docs` и `/openapi.json` проксируются на backend-контейнер.

## Проверка

```bash
python -m unittest
node --check frontend/app.js
```

Дополнительная документация:

- [backend/README.md](backend/README.md)
- [frontend/README.md](frontend/README.md)
- [algorithm/README.md](algorithm/README.md)
- [docs/DATA.md](docs/DATA.md)
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [docs/TESTING.md](docs/TESTING.md)
