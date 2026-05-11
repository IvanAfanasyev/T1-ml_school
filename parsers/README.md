# Parsers — облачные провайдеры РФ

Набор парсеров публичной информации по 4 облачным провайдерам:
**Cloud.ru**, **Selectel**, **Т1 Облако**, **VK Cloud**.

Каждый парсер собирает сырые данные (HTML, JSON, PDF), нормализует их под единую
схему и опционально обогащает результаты через LLM. Все 4 парсера используют
общие настройки (`.env`, конфиг, LLM-клиент) и пишут результаты в одну общую
папку `data/`.

---

## Структура проекта

```
Parsers/
├── .env                          # один общий файл с LLM-настройками
├── requirements.txt              # один общий список зависимостей
├── README.md                     # этот файл
├── aggregate_providers.py        # standalone-скрипт сборки общего providers.json
│
├── common/                       # общий код для всех парсеров
│   ├── config.py                 # Settings (LLM) + 4 функции с константами провайдеров:
│   │                             #   cloud_ru_config(), selectel_config(),
│   │                             #   t1_cloud_config(), vk_cloud_config()
│   ├── llm_client.py             # один общий ask_llm(...)
│   └── aggregate.py              # сборка per-provider providers.json в общий файл
│
├── data/                         # все собранные данные складываются сюда
│   ├── raw/{cloud-ru, selectel, t1_cloud, vk-cloud}/
│   └── normalized/
│       ├── providers.json                # ← общий файл со всеми 4 провайдерами
│       └── {cloud-ru, selectel, t1_cloud, vk-cloud}/   # остальные данные по парсеру
│
├── cloud_ru_parser/              # парсер Cloud.ru
│   ├── app/utils.py              # парсер-специфичные хелперы
│   ├── parse_*.py                # сбор сырых данных
│   ├── normalize_*.py            # нормализация
│   ├── llm_enrichment.py         # LLM-обогащение (категории, теги и т.д.)
│   └── run_cloud_ru_pipeline.py  # запуск всех шагов подряд
│
├── selectel_parser/              # парсер Selectel (та же раскладка)
├── vk_cloud_parser/              # парсер VK Cloud (та же раскладка)
│
└── t1_cloud_parser/             # парсер Т1 Облако
    ├── app/                      # normalizer, schemas, llm_enrichment
    ├── t1_provider_metadata_collector.py  # сбор метаданных + скачивание PDF тарифа
    ├── t1_tariff_pdf_parser.py            # извлечение таблиц из PDF
    ├── normalize_t1_strict_schema.py      # нормализация под общую схему
    └── run_t1_cloud_pipeline.py           # запуск всех шагов подряд
```

---

## Установка

```powershell
# 1. Создать виртуальное окружение (Python 3.10+)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Один раз поставить браузер для Playwright (нужен парсеру VK Cloud)
playwright install chromium
```

## Настройка `.env`

Один общий файл в корне `Parsers/.env`:

```
LLM_API_KEY=<ваш ключ>
LLM_BASE_URL=https://llm.api.cloud.yandex.net/v1
LLM_MODEL=gpt://b1gmp2jc7dsa2mp68k3p/yandexgpt-5.1/latest
```

`common/config.py` ищет `.env` в корне проекта, в текущем каталоге и рядом
с самим файлом конфига.

---

## Запуск

Каждый парсер запускается из своей папки. Pipeline-скрипты прогоняют все шаги
подряд (сбор сырых → нормализация → опционально LLM) и пишут лог в
`data/normalized/<provider>/parse_log.json`.

```powershell
# Cloud.ru
cd cloud_ru_parser
python run_cloud_ru_pipeline.py

# Selectel
cd ..\selectel_parser
python run_selectel_pipeline.py

# VK Cloud
cd ..\vk_cloud_parser
python run_vk_cloud_pipeline.py

# Т1 Облако
cd ..\t1_cloud_parser
python run_t1_cloud_pipeline.py
```

Любой отдельный шаг тоже можно запустить напрямую:

```powershell
cd cloud_ru_parser
python parse_cloud_provider.py
python normalize_cloud_services.py
```

### Переменные окружения для T1

В `normalize_t1_strict_schema.py` есть необязательные флаги:

- `USE_LLM_FOR_SERVICES=1` (по умолчанию **включено**) — обогащать `services.json` через LLM.
- `USE_LLM_FOR_PRICING_ITEMS=1` (по умолчанию **выключено**) — обогащать каждую тарифную строку.
- `LLM_PRICING_ITEMS_LIMIT=20` — ограничить число строк для теста.

```powershell
$env:USE_LLM_FOR_PRICING_ITEMS = "1"
$env:LLM_PRICING_ITEMS_LIMIT = "20"
python run_t1_cloud_pipeline.py
```

---

## Где лежат результаты

Все 4 парсера пишут в общий `Parsers/data/`.

### Сырые данные — `data/raw/<provider>/`

| Provider   | Файлы                                                                             |
|------------|-----------------------------------------------------------------------------------|
| cloud-ru   | `compliance_raw.json`, `regions_raw.json`, `tariff_index_raw.json`, `tariff_pages_raw.json` |
| selectel   | `compliance_raw.json`, `availability_raw.json`, `prices_raw.json`, `pricing_skipped_rows.json` |
| t1_cloud   | `t1_provider_metadata_raw.json`, `t1_current_tariff.pdf`, `t1_current_tariff_info.json`, `t1_tariff_items_raw.json`, `t1_tariff_items_raw.xlsx`, `t1_tariff_parser_meta.json` |
| vk-cloud   | `compliance_raw.json`, `regions_raw.json`, `pricelist_raw.json`                   |

### Нормализованные — `data/normalized/`

Общий файл (агрегируется из per-provider источников):

- **`data/normalized/providers.json`** — единый файл со всеми 4 провайдерами
  (платформа, регионы, 152-ФЗ и т.д.). Дедуп по `provider_id`.

Per-provider — `data/normalized/<provider>/`:

- `providers.json` — карточка одного провайдера (источник истины для общего файла)
- `services.json` — список сервисов с категорией / тегами
- `service_pricing_items.json` — тарифные позиции
- `parse_log.json` — лог прогона пайплайна (включает шаг `aggregate_providers`)
- `errors.json`, `llm_errors.json` — диагностика

Дополнительно у отдельных провайдеров:

- selectel: `service_availability.json`, `pricing_items_stats.json`
- vk-cloud: `pricing_items_stats.json`
- t1_cloud: `user_task_templates.json`

### Как работает агрегация `providers.json`

Каждый парсер в конце своего pipeline вызывает `aggregate_providers()` из
`common/aggregate.py`. Эта функция читает все
`data/normalized/<provider>/providers.json`, мерджит их в один список
(дедуп по `provider_id`) и пишет в `data/normalized/providers.json`.

Запустить агрегацию вручную (например, после ручного прогона отдельных
шагов нормализации):

```powershell
cd C:\Users\Самир\Desktop\Parsers
python aggregate_providers.py
```

---

## Зависимости (общая `requirements.txt`)

| Пакет              | Кто использует                                  |
|--------------------|--------------------------------------------------|
| `requests`         | все парсеры                                      |
| `beautifulsoup4`   | все парсеры (HTML-скрейпинг)                     |
| `playwright`       | vk_cloud_parser (рендеринг прайс-листа)          |
| `pdfplumber`       | t1_cloud_parser (PDF тарифа)                    |
| `pandas`           | t1-cloud, cloud_ru (таблицы)                     |
| `openpyxl`         | t1-cloud (`.xlsx` экспорт через pandas)          |
| `openai`           | LLM-клиент (через Yandex AI Studio совместимый API) |
| `pydantic`         | схемы (t1-cloud)                                 |
| `pydantic-settings`| общий `Settings` для `.env`                      |

---

## Как добавить нового провайдера

1. Создать папку `<new_provider_parser>/` рядом с существующими.
2. Добавить функцию `<new_provider>_config()` в `common/config.py` — она должна
   возвращать `SimpleNamespace` с полями `PROVIDER_ID`, `RAW_DIR`, `NORMALIZED_DIR`,
   нужными URL-ами и т.д. `RAW_DIR`/`NORMALIZED_DIR` создаются автоматически
   через `_provider_dirs(...)`.
3. В файлах парсера импортировать общий код:
   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

   from common.config import new_provider_config
   from common.llm_client import ask_llm
   ```
4. Парсер-специфичные хелперы класть в `<new_provider_parser>/app/utils.py`.
