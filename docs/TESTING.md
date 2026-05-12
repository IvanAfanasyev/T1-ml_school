# Тестирование и метрики

## Unit tests

```bash
python -m unittest
```

Покрывают:

- API search;
- dialog manager;
- query extractor;
- query validator;
- region resolver;
- pricing/budget logic;
- scoring;
- solution bundle;
- normalized data structure;
- evaluation metrics.

## Frontend syntax check

```bash
node --check frontend/app.js
```

## Golden Dataset

`data/evaluation/golden_dataset.json` содержит контрольные запросы и ожидаемое поведение.

Проверяются:

- релевантность top-3;
- 152-ФЗ;
- регион;
- fallback-регион;
- бюджет;
- инфраструктурная связка.

## Метрики

| Метрика | Что показывает |
|---|---|
| Precision@3 | сколько релевантных сервисов попало в top-3 |
| MRR | насколько высоко первый релевантный сервис |
| Compliance Pass Rate | корректно ли учтён 152-ФЗ |
| Region Match / Fallback Rate | корректность региона и ближайшего региона |
| Budget Handling Accuracy | корректность обработки бюджета и неизвестных цен |
| LLM Judge Overall Score | качество объяснения и полезность ответа |

## Скрипты

```bash
python -m algorithm.scripts.evaluate_ranking
python -m algorithm.scripts.evaluate_with_judge
```

## Ручные demo-тесты

| Сценарий | Запрос | Проверка |
|---|---|---|
| Compute + 152-ФЗ | `Веб-приложение на Python, нужен 152-ФЗ, бюджет 30000 рублей в месяц, Москва.` | compute, Москва, 152-ФЗ |
| PostgreSQL | `DBaaS с PostgreSQL для тестовой среды, бюджет 10 тысяч рублей.` | managed DB |
| Object Storage | `Хранилище для бэкапов, 500 ГБ, обязателен 152-ФЗ, любой регион РФ.` | S3, объём |
| Kubernetes | `Кластер Kubernetes для продакшена, 152-ФЗ обязателен, регион Санкт-Петербург.` | Managed Kubernetes |
| Логи | `Сервис для сбора и анализа логов, ELK-совместимое решение, бюджет до 50000 рублей.` | OpenSearch/Logging |
| Ближайший регион | `ВМ с 152-ФЗ во Владивостоке, до 10000 рублей.` | fallback-регион |
| Связка | `Backend на Python, PostgreSQL и object storage на 500 ГБ, 152-ФЗ, Москва.` | compute + DB + storage |
| Диалог | `Нужно подобрать облако для веб-приложения.` | уточняющие вопросы |

## Полная проверка перед push

```bash
python -m unittest
node --check frontend/app.js
git status
```
