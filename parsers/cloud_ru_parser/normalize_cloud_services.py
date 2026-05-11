from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import cloud_ru_config

_cfg = cloud_ru_config()
NORMALIZED_DIR = _cfg.NORMALIZED_DIR
PROVIDER_ID = _cfg.PROVIDER_ID
RAW_DIR = _cfg.RAW_DIR
TARIFF_INDEX_URL = _cfg.TARIFF_INDEX_URL

from app.utils import load_json, normalize_billing_period, normalize_price, normalize_unit, save_json, slugify
from llm_enrichment import enrich_service_with_llm

MAIN_ITEM_TYPES_BY_CATEGORY = {
    "Cloud Compute": {"cpu_ram_vm"},
    "Cloud Storage": {"storage"},
    "Database": {"database_instance"},
    "Network": {"network", "traffic"},
    "Containers and Serverless": {"container", "cpu_ram_vm"},
    "Messaging and Cache": {"message_queue", "database_instance"},
    "Security": {"security"},
}


def choose_price_from(service_id: str, category: str, pricing_items: list[dict]) -> tuple[float | None, str | None]:
    related = [x for x in pricing_items if x.get("service_id") == service_id and x.get("price_rub") is not None]
    if not related:
        return None, None

    main_types = MAIN_ITEM_TYPES_BY_CATEGORY.get(category, set())
    primary = [x for x in related if x.get("item_type") in main_types]
    candidates = primary or related
    best = min(candidates, key=lambda x: x.get("price_rub", float("inf")))
    return best.get("price_rub"), best.get("price_unit")


def main() -> None:
    index = load_json(RAW_DIR / "tariff_index_raw.json", [])
    provider = (load_json(NORMALIZED_DIR / "providers.json", []) or [{}])[0]
    pricing_items = load_json(NORMALIZED_DIR / "service_pricing_items.json", [])

    services = []
    for item in index:
        service_name = item["service_name"]
        service_id = f"{PROVIDER_ID}-{slugify(service_name)}"
        enrich = enrich_service_with_llm(service_name, item.get("title", ""))
        price_from, price_unit = choose_price_from(service_id, enrich["category"], pricing_items)

        services.append({
            "service_id": service_id,
            "provider_id": PROVIDER_ID,
            "name": service_name,
            "category": enrich["category"],
            "description": enrich["description"],
            "tech_stack_tags": enrich["tech_stack_tags"],
            "use_case_tags": enrich["use_case_tags"],
            "compliance_tags": provider.get("compliance_tags", ["152-FZ", "UZ-1"]),
            "regions": provider.get("regions", ["Russia", "RU-Moscow", "ru-moscow-1"]),
            "pricing_model": "pay-as-you-go",
            "price_from_rub": price_from,
            "price_unit": price_unit,
            "support_level": None,
            "service_url": item["tariff_url"],
            "source_url": item["tariff_url"],
            "tariff_index_url": TARIFF_INDEX_URL,
            "parsed_at": item.get("parsed_at"),
            "is_synthetic": False,
        })

    save_json(NORMALIZED_DIR / "services.json", services)
    print(f"Saved {len(services)} services: {NORMALIZED_DIR / 'services.json'}")


if __name__ == "__main__":
    main()
