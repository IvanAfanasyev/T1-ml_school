# Деплой

Production-схема:

```text
Пользователь
  -> Nginx
  -> frontend статикой
  -> /api проксируется в FastAPI backend
  -> Docker-контейнер backend
  -> data/normalized JSON
```

## Backend

Backend запускается через Docker Compose:

```bash
docker compose up -d --build
docker compose logs -f backend
```

Контейнер слушает порт `8000` внутри VM. Наружу его обычно не показывают напрямую: Nginx проксирует `/api`, `/health`, `/docs`, `/openapi.json`.

## Frontend

Frontend - это статические файлы:

```text
frontend/index.html
frontend/styles.css
frontend/app.js
```

На сервере их можно положить в `/var/www/cloud-marketplace/`:

```bash
sudo mkdir -p /var/www/cloud-marketplace
sudo rsync -a --delete frontend/ /var/www/cloud-marketplace/
```

## Nginx

Пример server block:

```nginx
server {
    listen 80;
    server_name _;

    root /var/www/cloud-marketplace;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
    }
}
```

После изменения:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Обновление сервера

```bash
git checkout main
git pull origin main
docker compose up -d --build
sudo rsync -a --delete frontend/ /var/www/cloudmatch/
sudo nginx -t
sudo systemctl reload nginx
```
