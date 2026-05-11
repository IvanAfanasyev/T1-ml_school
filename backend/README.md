# Backend

`backend/` - серверная часть CloudMatch. Она принимает HTTP-запросы от frontend, проверяет входные данные, вызывает алгоритм подбора и возвращает результат в формате JSON.

## Структура

```text
backend/
├── README.md
├── Dockerfile
├── requirements.txt
├── __init__.py
└── app/
    ├── __init__.py
    ├── main.py
    └── api/
        ├── __init__.py
        ├── chat.py
        └── search.py
```

## Основные файлы

`backend/app/main.py` создает FastAPI-приложение, подключает CORS и регистрирует API-маршруты.

`backend/app/api/chat.py` отвечает за диалоговый endpoint `POST /api/chat`. Он принимает сообщение пользователя, память текущего чата, флаги `with_explanation` и `include_debug`, затем вызывает диалоговый слой из `algorithm/`.

`backend/app/api/search.py` отвечает за прямой поиск, витрину и карточки сервисов. В этом файле находятся request/response модели для API, кеширование тяжелых объектов и преобразование внутренних моделей алгоритма в JSON для frontend.

`backend/Dockerfile` описывает сборку backend-контейнера.

`backend/requirements.txt` содержит Python-зависимости проекта.

## Endpoint-ы

### `GET /`

Возвращает краткую информацию о backend и список основных API.

### `GET /health`

Проверяет, что backend запущен.

Ожидаемый ответ:

```json
{
  "status": "ok"
}
```

### `POST /api/chat`

Основной endpoint для диалогового агента.

Вход:

```json
{
  "user_id": "local-user",
  "chat_id": "chat-id",
  "message": "база данных MySQL, москва, любой бюджет",
  "memory": null,
  "with_explanation": true,
  "include_debug": false
}
```

Что делает endpoint:

1. Передает сообщение в `DialogManager`.
2. Диалоговый слой решает, нужно ли уточнение.
3. Если данных достаточно, backend запускает поиск через `SearchPipeline`.
4. Результат приводится к frontend-friendly JSON.
5. Возвращается новое состояние памяти чата.

Важные поля ответа:

- `action` - `clarification`, `search` или `off_topic`;
- `message` - короткое сообщение агента;
- `needs_clarification` - нужно ли уточнение;
- `clarification_questions` - список вопросов;
- `search` - результат поиска, если подбор был запущен;
- `memory` - обновленная память чата.

### `POST /api/search`

Прямой поиск без диалогового сценария.

Подходит для технической проверки и случаев, когда frontend уже собрал полный запрос.

Вход:

```json
{
  "query": "PostgreSQL в Москве до 20000 рублей",
  "with_explanation": true,
  "include_debug": false
}
```

### `GET /api/catalog/services`

Возвращает сервисы для витрины без поиска и фильтров.

Параметры:

- `limit` - размер страницы;
- `offset` - смещение;
- `pricing_limit` - сколько тарифных позиций подтянуть к карточке.

### `GET /api/catalog/services/{service_id}`

Возвращает подробную карточку сервиса: описание, теги, регионы, ссылку и тарифные позиции.

## Как backend связан с algorithm

Backend сам не ранжирует сервисы. Он только принимает запрос, вызывает алгоритм и отдает ответ наружу.

Главные связи:

```text
backend/app/api/chat.py
  -> algorithm/cloudmatch/agent/dialog.py
  -> backend/app/api/search.py
  -> algorithm/cloudmatch/agent/pipeline.py

backend/app/api/search.py
  -> algorithm/cloudmatch/data/
  -> algorithm/cloudmatch/retrieval/
  -> algorithm/cloudmatch/ranking/
  -> algorithm/cloudmatch/agent/user_response_formatter.py
```

## Память чата

Backend не хранит чаты в базе. Память приходит от frontend в поле `memory` и возвращается обратно обновленной.

Это значит:

- история одного чата живет в браузере пользователя;
- backend остается stateless;
- для MVP не нужна регистрация и таблица пользователей;
- если пользователь очистит localStorage, история пропадет.

## Ошибки

Основные типы ошибок:

- `400` - пустой поисковый запрос;
- `404` - сервис не найден в карточке каталога;
- `503` - не хватает данных, индекса, `.env` или есть проблема с LLM/файлами.

## Локальный запуск

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Swagger UI:

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Docker

Контейнер собирается из корня проекта, но использует `backend/Dockerfile`.

```bash
docker compose up -d --build
docker compose logs -f backend
```

Внутри Docker build выполняется:

```bash
python -m algorithm.scripts.build_indexes
```

Поэтому в репозиторий не нужно добавлять `data/indexes/`: индекс создается при сборке.

## Переменные окружения

Backend ожидает `.env` в корне проекта.

Минимальные переменные:

```text
LLM_API_KEY=...
LLM_BASE_URL=...
LLM_MODEL=...
```

Пример лежит в `.env.example`.
