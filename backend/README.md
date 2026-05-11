# Backend

Папка `backend/` содержит серверную часть проекта.

```text
backend/
  app/
    main.py          FastAPI-приложение и маршруты
    api/
      chat.py        API диалогового агента
      search.py      API поиска, витрины и карточек сервисов
  Dockerfile         Сборка backend-контейнера
  requirements.txt   Python-зависимости
```

Backend отвечает за:

- прием HTTP-запросов от frontend;
- валидацию request/response моделей;
- запуск диалогового агента;
- запуск поиска и ранжирования;
- выдачу каталога сервисов и тарифных позиций;
- прокидывание результатов во frontend в стабильном JSON-формате.

Локальный запуск:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

В Docker backend запускается командой из `backend/Dockerfile`:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
