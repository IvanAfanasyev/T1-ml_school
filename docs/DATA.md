# Данные

## Принципы

CloudMatch использует только публичные данные российских облачных провайдеров:

- без авторизации;
- без личных кабинетов;
- без платных отчётов;
- без персональных данных;
- с фиксацией URL и даты сбора, если источник проходит через парсер.

## Провайдеры

- Т1 Облако;
- Cloud.ru;
- Selectel;
- VK Cloud.

## Источники

### Т1 Облако

- https://t1-cloud.ru/documents/services
- https://t1-cloud.ru/documents/rates
- https://t1-cloud.ru/docs

### Cloud.ru

- https://cloud.ru/services
- https://cloud.ru/pricing
- https://cloud.ru/documents/tariffs

### Selectel

- https://selectel.ru/services/cloud/
- https://selectel.ru/prices/
- https://docs.selectel.ru/
- https://selectel.ru/about/security/

### VK Cloud

- https://cloud.vk.com/cloud-platform/
- https://cloud.vk.com/pricing/
- https://cloud.vk.com/docs/
- https://cloud.vk.com/certificates/

## Файлы

```text
data/normalized/
├── providers.json
├── services.json
├── service_pricing_items.json
├── parse_log.json
└── errors.json
```

## providers.json

Провайдеры.

Основные поля:

- `provider_id`;
- `name`;
- `base_platform`;
- `is_152fz_compliant`;
- `regions`;
- `api_docs_url`;
- `pricing_url`;
- `source_url`.

## services.json

Сервисы.

Основные поля:

- `service_id`;
- `provider_id`;
- `name`;
- `category`;
- `description`;
- `tech_stack_tags`;
- `use_case_tags`;
- `compliance_tags`;
- `regions`;
- `pricing_model`;
- `price_from_rub`;
- `price_unit`;
- `service_url`;
- `source_url`.

## service_pricing_items.json

Тарифные позиции.

Основные поля:

- `pricing_item_id`;
- `service_id`;
- `item_name`;
- `item_type`;
- `price_rub`;
- `price_unit`;
- `billing_period`;
- `region`;
- `configuration_tags`;
- `source_url`.

## parse_log.json

Лог сбора: дата, провайдер, URL, статус, количество записей, предупреждения.

## errors.json

Ошибки парсинга и нормализации.

## Жизненный цикл данных

```text
parsers
  -> parsers/data/normalized
  -> algorithm.scripts.import_parser_data
  -> data/normalized
  -> algorithm.scripts.build_indexes
  -> data/indexes
  -> backend search
```

Команды:

```bash
python -m algorithm.scripts.import_parser_data --source-dir parsers/data/normalized
python -m algorithm.scripts.build_indexes
```

## Тарифные позиции

Цена в каталоге не всегда равна стоимости готового решения. Это может быть цена за:

- vCPU;
- RAM;
- диск;
- 1 ГБ;
- час;
- месяц;
- штуку;
- минимальную конфигурацию.

Примеры корректного отображения:

```text
от 280,78 ₽/мес за vCPU
Итоговая стоимость ВМ зависит от RAM, диска, сети, IP и дополнительных опций.
```

```text
от 852,40 ₽/мес за 500 ГБ
```

```text
Cold storage: подходит для редкого доступа; стоимость чтения, восстановления и API-операций нужно проверять отдельно.
```

## Golden Dataset

```text
data/evaluation/golden_dataset.json
```

Используется для проверки `Precision@3`, `MRR`, compliance, budget и region matching.
