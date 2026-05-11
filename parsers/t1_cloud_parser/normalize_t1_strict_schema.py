import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import t1_cloud_config

from app.normalizer import (
    build_services_from_pricing_items,
    normalize_pricing_item,
    normalize_provider_from_metadata,
)
from app.llm_enrichment import (
    enrich_pricing_items_with_llm,
    enrich_services_with_llm,
)
from app.schemas import NormalizationError, ParseLogRecord, UserTaskTemplate


_cfg = t1_cloud_config()


# =========================
# Входные файлы
# =========================

RAW_PROVIDER_METADATA_FILE = _cfg.RAW_DIR / "t1_provider_metadata_raw.json"
RAW_TARIFF_ITEMS_FILE = _cfg.RAW_DIR / "t1_tariff_items_raw.json"


# =========================
# Выход строго как в PDF-документе
# =========================

OUTPUT_DIR = _cfg.NORMALIZED_DIR

PROVIDERS_OUTPUT_FILE = OUTPUT_DIR / "providers.json"
SERVICES_OUTPUT_FILE = OUTPUT_DIR / "services.json"
SERVICE_PRICING_ITEMS_OUTPUT_FILE = OUTPUT_DIR / "service_pricing_items.json"
USER_TASK_TEMPLATES_OUTPUT_FILE = OUTPUT_DIR / "user_task_templates.json"
PARSE_LOG_OUTPUT_FILE = OUTPUT_DIR / "parse_log.json"
ERRORS_OUTPUT_FILE = OUTPUT_DIR / "errors.json"
LLM_ERRORS_OUTPUT_FILE = OUTPUT_DIR / "llm_errors.json"


# =========================
# LLM настройки
# =========================

# По умолчанию LLM включена только для services.
# Для 32 сервисов это нормально.
USE_LLM_FOR_SERVICES = os.getenv("USE_LLM_FOR_SERVICES", "1") == "1"

# Для 375 тарифных строк LLM по умолчанию выключена.
# Если захочешь включить:
# set USE_LLM_FOR_PRICING_ITEMS=1
USE_LLM_FOR_PRICING_ITEMS = os.getenv("USE_LLM_FOR_PRICING_ITEMS", "0") == "1"

# Можно ограничить количество тарифных строк для теста:
# set LLM_PRICING_ITEMS_LIMIT=20
_limit = os.getenv("LLM_PRICING_ITEMS_LIMIT")
LLM_PRICING_ITEMS_LIMIT = int(_limit) if _limit else None


def read_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def build_test_tasks() -> list[dict]:
    tasks = [
        UserTaskTemplate(
            id=1,
            task_category="web-hosting",
            tech_stack=["Python", "PostgreSQL", "Docker"],
            use_case_tags=["web-hosting", "backend", "database"],
            budget_range_rub="10000-50000",
            compliance_required=True,
            region="Russia",
            created_for_testing=True,
        ),
        UserTaskTemplate(
            id=2,
            task_category="object-storage",
            tech_stack=["S3", "API"],
            use_case_tags=["backup", "media-storage", "data-storage"],
            budget_range_rub="1000-20000",
            compliance_required=True,
            region="Russia",
            created_for_testing=True,
        ),
        UserTaskTemplate(
            id=3,
            task_category="machine-learning",
            tech_stack=["GPU", "Python", "ML"],
            use_case_tags=["machine-learning", "ai"],
            budget_range_rub="50000-500000",
            compliance_required=False,
            region="Russia",
            created_for_testing=True,
        ),
    ]

    return [task.model_dump(mode="json") for task in tasks]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    parse_log = []
    errors = []
    llm_errors = []

    raw_provider_metadata = read_json(RAW_PROVIDER_METADATA_FILE)
    raw_tariff_items = read_json(RAW_TARIFF_ITEMS_FILE)

    if not isinstance(raw_tariff_items, list):
        raise ValueError(f"{RAW_TARIFF_ITEMS_FILE} must contain a list")

    # 1. providers.json
    provider = normalize_provider_from_metadata(raw_provider_metadata)
    providers = [provider.model_dump(mode="json")]
    write_json(PROVIDERS_OUTPUT_FILE, providers)

    parse_log.append(
        ParseLogRecord(
            provider_id=provider.provider_id,
            url=provider.source_url,
            status="success",
            records_added=1,
            error=None,
        ).model_dump(mode="json")
    )

    # 2. service_pricing_items.json
    pricing_items = []

    for raw_item in raw_tariff_items:
        try:
            pricing_item = normalize_pricing_item(raw_item, provider)
            pricing_items.append(pricing_item)
        except Exception as error:
            errors.append(
                NormalizationError(
                    item_type="service_pricing_item",
                    provider_id=raw_item.get("provider_id", provider.provider_id),
                    source_url=raw_item.get("source_file") or provider.pricing_url or provider.source_url,
                    error=str(error),
                    raw_item=raw_item,
                ).model_dump(mode="json")
            )

    pricing_items_dicts = [item.model_dump(mode="json") for item in pricing_items]

    parse_log.append(
        ParseLogRecord(
            provider_id=provider.provider_id,
            url=provider.pricing_url or provider.source_url,
            status="success" if not errors else "partial_success",
            records_added=len(pricing_items_dicts),
            error=None if not errors else f"errors: {len(errors)}",
        ).model_dump(mode="json")
    )

    # 3. services.json из pricing_items
    services = build_services_from_pricing_items(pricing_items, provider)
    services_dicts = [service.model_dump(mode="json") for service in services]

    # 4. LLM enrichment для services
    if USE_LLM_FOR_SERVICES:
        services_dicts, service_llm_errors = enrich_services_with_llm(
            services=services_dicts,
            pricing_items=pricing_items_dicts,
            enabled=True,
        )
        llm_errors.extend(service_llm_errors)

        parse_log.append(
            ParseLogRecord(
                provider_id=provider.provider_id,
                url="llm://services-enrichment",
                status="success" if not service_llm_errors else "partial_success",
                records_added=len(services_dicts) - len(service_llm_errors),
                error=None if not service_llm_errors else f"llm_errors: {len(service_llm_errors)}",
            ).model_dump(mode="json")
        )

    # 5. LLM enrichment для pricing_items, по умолчанию выключено
    if USE_LLM_FOR_PRICING_ITEMS:
        pricing_items_dicts, pricing_llm_errors = enrich_pricing_items_with_llm(
            pricing_items=pricing_items_dicts,
            services=services_dicts,
            enabled=True,
            max_items=LLM_PRICING_ITEMS_LIMIT,
        )
        llm_errors.extend(pricing_llm_errors)

        parse_log.append(
            ParseLogRecord(
                provider_id=provider.provider_id,
                url="llm://service-pricing-items-enrichment",
                status="success" if not pricing_llm_errors else "partial_success",
                records_added=len(pricing_items_dicts) - len(pricing_llm_errors),
                error=None if not pricing_llm_errors else f"llm_errors: {len(pricing_llm_errors)}",
            ).model_dump(mode="json")
        )

    # 6. Записываем итоговые service_pricing_items и services
    write_json(SERVICE_PRICING_ITEMS_OUTPUT_FILE, pricing_items_dicts)
    write_json(SERVICES_OUTPUT_FILE, services_dicts)

    parse_log.append(
        ParseLogRecord(
            provider_id=provider.provider_id,
            url=provider.pricing_url or provider.source_url,
            status="success",
            records_added=len(services_dicts),
            error=None,
        ).model_dump(mode="json")
    )

    # 7. user_task_templates.json
    user_task_templates = build_test_tasks()
    write_json(USER_TASK_TEMPLATES_OUTPUT_FILE, user_task_templates)

    parse_log.append(
        ParseLogRecord(
            provider_id=provider.provider_id,
            url="synthetic://user_task_templates",
            status="success",
            records_added=len(user_task_templates),
            error=None,
        ).model_dump(mode="json")
    )

    # 8. logs
    write_json(PARSE_LOG_OUTPUT_FILE, parse_log)
    write_json(ERRORS_OUTPUT_FILE, errors)
    write_json(LLM_ERRORS_OUTPUT_FILE, llm_errors)

    print("Готово")
    print(f"Providers:              {PROVIDERS_OUTPUT_FILE} ({len(providers)})")
    print(f"Services:               {SERVICES_OUTPUT_FILE} ({len(services_dicts)})")
    print(f"Service pricing items:  {SERVICE_PRICING_ITEMS_OUTPUT_FILE} ({len(pricing_items_dicts)})")
    print(f"User task templates:    {USER_TASK_TEMPLATES_OUTPUT_FILE} ({len(user_task_templates)})")
    print(f"Parse log:              {PARSE_LOG_OUTPUT_FILE}")
    print(f"Errors:                 {ERRORS_OUTPUT_FILE} ({len(errors)})")
    print(f"LLM errors:             {LLM_ERRORS_OUTPUT_FILE} ({len(llm_errors)})")


if __name__ == "__main__":
    main()
