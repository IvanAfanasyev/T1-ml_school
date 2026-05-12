# Deployment

## Production-схема

```text
Browser
  -> Nginx static frontend
  -> /api proxy
  -> FastAPI backend in Docker
```

Frontend лежит в:

```text
/var/www/cloud-marketplace/
```

Backend слушает:

```text
127.0.0.1:8000
```

## Обновление сервера

```bash
ssh -i ~/.ssh/cloud-marketplace-yc yc-user@51.250.18.102

cd /home/yc-user/t1_ml_school
git switch main
git pull origin main

sudo docker compose up -d --build

sudo rsync -a --delete frontend/ /var/www/cloud-marketplace/

sudo nginx -t
sudo systemctl reload nginx

sudo docker compose ps
curl -i http://127.0.0.1:8000/health
curl -I http://127.0.0.1
```

## Nginx

Проверить конфиг:

```bash
sudo nginx -t
```

Найти root/proxy:

```bash
sudo nginx -T 2>/dev/null | grep -E "root |proxy_pass|server_name|listen"
```

## Troubleshooting

### Docker permission denied

```bash
sudo docker compose up -d --build
```

Или:

```bash
sudo usermod -aG docker yc-user
```

Затем выйти и зайти заново.

### SSH publickey

```bash
ssh -i ~/.ssh/cloud-marketplace-yc yc-user@51.250.18.102
```

### Frontend не обновился

```bash
sudo nginx -T 2>/dev/null | grep root
sudo rsync -a --delete frontend/ /var/www/cloud-marketplace/
sudo systemctl reload nginx
```

В браузере: `Cmd + Shift + R`.

### Backend не отвечает

```bash
sudo docker compose ps
sudo docker compose logs -f backend
curl -i http://127.0.0.1:8000/health
```
