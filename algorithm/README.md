# Algorithm

`algorithm/` содержит основную логику CloudMatch: агент, retrieval, ranking, объяснения и оценку качества.

## Структура

```text
algorithm/
├── cloudmatch/
│   ├── agent/
│   ├── retrieval/
│   ├── ranking/
│   ├── data/
│   ├── geo/
│   ├── evaluation/
│   ├── llm/
│   └── schemas/
└── scripts/
```

## Pipeline

```text
DialogManager
  -> QueryExtractor
  -> QueryValidator
  -> hard filters
  -> HybridRetriever
  -> top-30 candidates
  -> pricing / budget / entity matching
  -> final scoring
  -> top provider selection / bundle builder
  -> explanation
  -> response formatter
```

## Retrieval

Используется hybrid retrieval:

```text
retrieval_score = 0.7 * embedding_score + 0.3 * bm25_score
```

- embeddings — смысловая близость;
- BM25 — точные совпадения терминов.

После retrieval берутся top-30 кандидатов.

## Entity Match

`entity_match_score` показывает совпадение сервиса со структурой запроса.

| Группа | Вес |
|---|---:|
| component | 0.30 |
| tech_stack | 0.25 |
| use_case | 0.15 |
| budget | 0.15 |
| requirements | 0.15 |

## Final Score

```text
final_score = 0.7 * retrieval_score + 0.3 * entity_match_score
```

## Top-3 провайдера

Для одиночного запроса система стремится показать `Top-3 провайдера`. Если точных совпадений меньше, выдача добирается fallback-кандидатами с пояснением.

## Связки

Если запрос требует несколько компонентов, например:

```text
compute + database + storage
```

система собирает инфраструктурную связку. Для связок допустимо меньше трёх результатов.

## Fallback-регионы

Если точного региона нет, система может предложить ближайший доступный регион и явно объяснить замену.

## Форматирование цен

Цены показываются с единицей тарификации:

- за vCPU;
- за RAM;
- за 1 ГБ;
- за час;
- за месяц;
- за минимальную конфигурацию.

Это нужно, чтобы тарифная позиция не выглядела как полная цена готового решения.

## Evaluation

В `evaluation/` находятся:

- golden dataset;
- метрики;
- LLM Judge.

Команды:

```bash
python -m algorithm.scripts.evaluate_ranking
python -m algorithm.scripts.evaluate_with_judge
```

## Скрипты

```text
build_indexes.py
evaluate_ranking.py
evaluate_with_judge.py
generate_golden_dataset.py
import_parser_data.py
run_search_demo.py
run_search_demo_user.py
```
