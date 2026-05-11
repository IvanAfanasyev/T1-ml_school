from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import vk_cloud_config

_cfg = vk_cloud_config()
RAW_DIR = _cfg.RAW_DIR
NORMALIZED_DIR = _cfg.NORMALIZED_DIR
PROVIDER_ID = _cfg.PROVIDER_ID
PRICING_URL = _cfg.PRICELIST_URL

from app.utils import load_json, save_json
from llm_enrichment import enrich_service_with_llm


MAIN_ITEM_TYPES_BY_CATEGORY = {
    "Cloud Compute": {"cpu_ram_vm", "compute", "storage"},
    "Cloud Storage": {"storage"},
    "Database": {"database_instance", "storage"},
    "Network": {"network", "traffic"},
    "Containers and Serverless": {"container", "cpu_ram_vm", "storage"},
    "Messaging and Cache": {"message_queue", "database_instance", "storage"},
    "Security": {"security"},
    "Data and Analytics": {"database_instance", "storage", "cpu_ram_vm", "other"},
    "Monitoring and DevOps": {"monitoring", "other"},
    "Developer Tools": {"request", "other"},
    "Cloud Service": {"cpu_ram_vm", "storage", "database_instance", "network", "other"},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _service_is_152fz(name: str) -> bool:
    low = name.lower()
    return any(x in low for x in [
        "виртуальные серверы",
        "virtual servers",
        "cloud servers",
        "виртуальные рабочие места",
    ])


def _price_from(items: list[dict[str, Any]], category: str) -> tuple[float | None, str | None]:
    if not items:
        return None, None

    allowed = MAIN_ITEM_TYPES_BY_CATEGORY.get(category, set())
    candidates = [
        x for x in items
        if x.get("price_rub") is not None
        and not x.get("price_on_request")
        and (not allowed or x.get("item_type") in allowed)
    ]

    if not candidates:
        candidates = [
            x for x in items
            if x.get("price_rub") is not None and not x.get("price_on_request")
        ]

    if not candidates:
        return None, None

    best = min(candidates, key=lambda x: float(x["price_rub"]))
    return float(best["price_rub"]), best.get("price_unit")


def main() -> None:
    raw = load_json(RAW_DIR / "pricelist_raw.json")
    providers = load_json(NORMALIZED_DIR / "providers.json")
    pricing_items = load_json(NORMALIZED_DIR / "service_pricing_items.json")

    provider = providers[0] if providers else {}
    services_raw = raw.get("services", [])

    by_service: dict[str, list[dict[str, Any]]] = {}
    for item in pricing_items:
        by_service.setdefault(item["service_id"], []).append(item)

    services: list[dict[str, Any]] = []
    llm_errors: list[dict[str, str]] = []

    for raw_service in services_raw:
        service_id = raw_service["service_id"]
        name = raw_service["service_name"]

        try:
            enriched = enrich_service_with_llm(service_name=name, title=name)
        except Exception as exc:
            llm_errors.append({
                "service_id": service_id,
                "service_name": name,
                "error": str(exc),
            })
            enriched = {
                "category": "Cloud Service",
                "description": f"Облачный сервис VK Cloud: {name}.",
                "tech_stack_tags": [],
                "use_case_tags": [],
            }

        price, unit = _price_from(by_service.get(service_id, []), enriched["category"])
        is_152fz = _service_is_152fz(name)

        service = {
            "service_id": service_id,
            "provider_id": PROVIDER_ID,
            "name": name,
            "category": enriched["category"],
            "description": enriched["description"],
            "tech_stack_tags": enriched["tech_stack_tags"],
            "use_case_tags": enriched["use_case_tags"],
            "is_152fz_compliant": is_152fz,
            "compliance_tags": (
                ["152-FZ", "UZ-1", "ISPDN"] if is_152fz else ["152-FZ-available"]
            ),
            "compliance_note": (
                provider.get("compliance_note")
                if is_152fz else
                "У VK Cloud есть услуга «Облако ФЗ-152», но для этого сервиса требуется отдельная проверка принадлежности к аттестованному периметру."
            ),
            "regions": provider.get("regions", []),
            "availability_zones": provider.get("availability_zones", []),
            "pricing_model": "pay-as-you-go",
            "price_from_rub": price,
            "price_from_value": price,
            "price_unit": unit,
            "support_level": None,
            "service_url": PRICING_URL,
            "source_url": PRICING_URL,
            "parsed_at": _utc_now(),
            "is_synthetic": False,
        }
        services.append(service)

    save_json(NORMALIZED_DIR / "services.json", services)
    save_json(NORMALIZED_DIR / "llm_errors.json", llm_errors)


if __name__ == "__main__":
    main()
