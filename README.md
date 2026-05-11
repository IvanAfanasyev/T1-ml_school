# CloudMatch

CloudMatch - MVP-сервис для подбора российских облачных сервисов по обычному пользовательскому запросу. Пользователь описывает задачу, backend извлекает параметры, ищет по нормализованному каталогу и возвращает рекомендации: одиночный top-3 или связку сервисов под несколько ролей.

## Структура

```text
backend/                 FastAPI-приложение и Dockerfile backend
frontend/                Статический интерфейс сайта
algorithm/cloudmatch/    Извлечение запроса, диалог, retrieval, ranking, форматирование ответа
algorithm/scripts/       Служебные команды для индексов, импорта данных и демо
data/normalized/         Нормализованные JSON-данные провайдеров, сервисов и тарифов
data/evaluation/         Тестовый набор для проверки качества ранжирования
docs/                    Короткая документация по запуску, данным, тестам и деплою
tests/                   Юнит-тесты backend и алгоритма
```

## Быстрый запуск локально

1. Создать окружение и поставить зависимости:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

2. Настроить LLM:

```bash
cp .env.example .env
```

В `.env` нужно указать ключ, base URL и модель.

3. Построить embedding-индекс:

```bash
python -m algorithm.scripts.build_indexes
```

4. Запустить backend:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

5. Открыть API-документацию:

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

6. Открыть frontend:

Можно открыть файл `frontend/index.html` в браузере. Если frontend отдается через Nginx или другой сервер с того же домена, он сам будет обращаться к `/api/...`. При локальном открытии он обращается к `http://127.0.0.1:8000`.

## API

Основные endpoint:

- `GET /health` - проверка, что backend жив.
- `POST /api/chat` - диалоговый агент с памятью одного чата.
- `POST /api/search` - прямой поиск без диалоговых уточнений.
- `GET /api/catalog/search` - витрина сервисов.
- `GET /api/catalog/services/{service_id}` - подробная карточка сервиса с тарифными позициями.

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

## Как работает подбор

1. LLM извлекает структуру запроса: тип запроса, технологии, регион, бюджет, компоненты решения.
2. Диалоговый слой уточняет недостающие параметры, если запрос слишком короткий.
3. Retrieval находит кандидатов по embeddings и BM25.
4. Ranking считает совпадение технологий, сценариев, компонентов, региона, бюджета и тарифов.
5. Для обычного запроса возвращается top-3 сервисов.
6. Для комплексного запроса возвращаются связки сервисов. Каждая связка собирается из сервисов одного провайдера, чтобы backend, база, storage, backup и balancer были согласованы между собой.

## Данные

Основной каталог лежит в `data/normalized/`:

- `providers.json` - провайдеры.
- `services.json` - облачные сервисы.
- `service_pricing_items.json` - тарифные позиции.
- `parse_log.json` - информация о сборе данных.
- `errors.json` - ошибки нормализации, если были.

После обновления JSON нужно перестроить индекс:

```bash
python -m algorithm.scripts.build_indexes
```

## Docker

Backend собирается из `backend/Dockerfile`, а `docker-compose.yml` запускает контейнер на порту `8000`.

```bash
docker compose up -d --build
docker compose logs -f backend
```

Frontend в production отдается Nginx как статические файлы из папки `frontend/`, а запросы `/api`, `/health`, `/docs`, `/openapi.json` проксируются на backend-контейнер.

## Проверка

```bash
python -m unittest
node --check frontend/app.js
```

Подробности:

- [docs/TESTING.md](docs/TESTING.md)
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [docs/DATA.md](docs/DATA.md)
