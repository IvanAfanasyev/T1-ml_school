# Parsers

`parsers/` содержит парсеры публичных данных провайдеров.

## Провайдеры

```text
cloud_ru_parser/
selectel_parser/
t1_cloud_parser/
vk_cloud_parser/
common/
data/
```

## Правила

Используются только публичные данные:

- без авторизации;
- без личных кабинетов;
- без платных отчётов;
- без персональных данных.

## Установка macOS/Linux

```bash
cd parsers
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Результат парсинга

```text
parsers/data/normalized/
```

## Импорт в основной проект

Из корня проекта:

```bash
python -m algorithm.scripts.import_parser_data --source-dir parsers/data/normalized
python -m algorithm.scripts.build_indexes
```

## Не коммитить

```text
parsers/.env
parsers/.env.*
parsers/data/raw/
__pycache__/
*.pyc
.venv/
```
