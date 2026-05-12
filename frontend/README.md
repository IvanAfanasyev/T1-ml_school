# Frontend

Frontend — статический интерфейс CloudMatch.

## Структура

```text
frontend/
├── index.html
├── styles.css
└── app.js
```

## Вкладки

### Витрина

Показывает каталог облачных сервисов.

### Агент

Основной экран демо:

- принимает запрос;
- отображает уточняющие вопросы;
- показывает top-3 провайдера;
- показывает связки;
- выводит совпавшие критерии;
- показывает объяснение.

### О проекте

Краткое описание продукта и ссылки.

## API base

Frontend выбирает API base автоматически:

- локально: `http://127.0.0.1:8000`;
- production: относительный путь `/api/*`;
- можно переопределить через `window.CLOUDMATCH_API_BASE`.

## LocalStorage

История диалога хранится в браузере через `localStorage`. Backend не хранит историю чата в БД.

## Локальный запуск

```bash
python3 -m http.server 5173 -d frontend
```

Открыть:

```text
http://127.0.0.1:5173
```

Backend должен быть запущен на `127.0.0.1:8000`.

## Обновление на сервере

```bash
cd /home/yc-user/t1_ml_school
sudo rsync -a --delete frontend/ /var/www/cloud-marketplace/
sudo nginx -t
sudo systemctl reload nginx
```

Если видна старая версия — сделать `Cmd + Shift + R`.

## Если backend недоступен

Проверить:

```bash
curl -i http://127.0.0.1:8000/health
```

Проверить Nginx:

```bash
sudo nginx -T 2>/dev/null | grep -E "root |proxy_pass|server_name|listen"
```
