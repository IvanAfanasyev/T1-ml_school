# Backend

Backend — FastAPI-приложение, которое связывает frontend и algorithm layer.

## Структура

```text
backend/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py
    └── api/
        ├── chat.py
        └── search.py
```

## Назначение

Backend отвечает за:

- HTTP API;
- healthcheck;
- запуск диалогового агента;
- прямой поиск;
- выдачу каталога;
- форматирование ответа для frontend.

## Endpoint'ы

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/` | информация об API |
| GET | `/health` | healthcheck |
| POST | `/api/chat` | диалоговый агент |
| POST | `/api/search` | прямой поиск |
| GET | `/api/catalog` | каталог |
| GET | `/api/catalog/search` | поиск по каталогу |
| GET | `/api/catalog/services/{service_id}` | карточка сервиса |

## Проверка

```bash
curl -i http://127.0.0.1:8000/health
```

Пример поиска:

```bash
curl -X POST http://127.0.0.1:8000/api/search   -H "Content-Type: application/json"   -d '{"query":"ВМ с 152-ФЗ в Москве до 30000 рублей","with_explanation":true}'
```

## Кэширование

Backend переиспользует тяжёлые объекты:

- `SearchPipeline`;
- `DataRepository`;
- `PricingRepository`.

Это снижает задержку повторных запросов.

## Локальный запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m algorithm.scripts.build_indexes
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

## Docker

```bash
docker compose up -d --build
docker compose ps
curl -i http://127.0.0.1:8000/health
```

Если нет прав на Docker:

```bash
sudo docker compose up -d --build
```

## Диагностика

```bash
sudo docker compose ps
sudo docker compose logs -f backend
sudo ss -tulpn | grep 8000
curl -i http://127.0.0.1:8000/health
```

Типовые причины проблем:

- не установлен `.env`;
- не построены индексы;
- нет файлов в `data/normalized`;
- контейнер не запущен;
- Docker требует `sudo`.
