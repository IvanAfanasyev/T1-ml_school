from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import selectel_config

_cfg = selectel_config()
PROVIDER_ID = _cfg.PROVIDER_ID
PROVIDER_NAME = _cfg.PROVIDER_NAME
PRICING_URL = _cfg.PRICING_URL
AVAILABILITY_URL = _cfg.AVAILABILITY_URL
COMPLIANCE_URL = _cfg.COMPLIANCE_URL
NORMALIZED_DIR = _cfg.NORMALIZED_DIR
RAW_DIR = _cfg.RAW_DIR

from app.utils import load_json, save_json, clean_text, slugify, utc_now_iso
from llm_enrichment import enrich_service_with_llm, rule_based_category


def _load_availability_map() -> dict[str, dict[str, Any]]:
    items = load_json(NORMALIZED_DIR / "service_availability.json", []) or []
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        key = slugify(item.get("service_name", ""))
        if key:
            result[key] = item
    return result


def _service_compliance(service_name: str, availability: dict[str, Any] | None) -> tuple[bool, list[str], str]:
    s = service_name.lower()
    certified_by_name = any(x in s for x in ["а-цод", "аттестован", "средства защиты информации", "сертифицирован"])
    certified_by_availability = bool(availability and availability.get("is_certified_segment_available"))

    if certified_by_name or certified_by_availability:
        return True, ["152-FZ", "UZ-1"], (
            "Для Selectel подтверждена возможность работы в аттестованном сегменте: "
            "А-ЦОД соответствует требованиям 152-ФЗ и УЗ-1. Доступность конкретного продукта "
            "берется из матрицы доступности."
        )

    # Cloud servers in Selectel marketing mention 152-FZ; for strictness mark only available, not guaranteed.
    return False, ["152-FZ-available"], (
        "У Selectel есть А-ЦОД/аттестованные сегменты для 152-ФЗ, но для этого сервиса требуется "
        "отдельная проверка размещения именно в аттестованном сегменте."
    )


def normalize_services() -> list[dict[str, Any]]:
    pricing_items = load_json(NORMALIZED_DIR / "service_pricing_items.json", []) or []
    availability_map = _load_availability_map()

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in pricing_items:
        grouped[item["service_id"]].append(item)

    services: list[dict[str, Any]] = []
    llm_errors: list[dict[str, Any]] = []

    for service_id, items in grouped.items():
        service_name = items[0].get("service_name") or service_id.replace(f"{PROVIDER_ID}-", "")
        avail = availability_map.get(slugify(service_name))
        raw_hint = "\n".join(x.get("raw_text", "") for x in items[:8])

        try:
            enrichment = enrich_service_with_llm(service_name, raw_hint)
        except Exception as e:
            enrichment = {
                "category": rule_based_category(service_name),
                "description": f"Сервис Selectel «{clean_text(service_name)}» используется для облачной инфраструктуры.",
                "tech_stack_tags": [],
                "use_case_tags": [],
            }
            llm_errors.append({"service_id": service_id, "service_name": service_name, "error": str(e)})

        valid_prices = [x for x in items if x.get("price_rub") is not None and not x.get("price_on_request")]
        # prefer monthly prices — hourly micro-items (0.005 руб/час) give misleading minimums
        monthly = [x for x in valid_prices if x.get("billing_period") == "month"]
        candidates = monthly if monthly else valid_prices
        cheapest = min(candidates, key=lambda x: float(x["price_rub"])) if candidates else None

        is_152, compliance_tags, compliance_note = _service_compliance(service_name, avail)

        regions = []
        pools = []
        for x in items:
            if x.get("region") and x.get("region") not in regions:
                regions.append(x["region"])
            if x.get("pool") and x.get("pool") not in pools:
                pools.append(x["pool"])
        if avail:
            for r in avail.get("regions", []):
                if r not in regions:
                    regions.append(r)
            for p in avail.get("pools", []):
                if p not in pools:
                    pools.append(p)

        services.append({
            "service_id": service_id,
            "provider_id": PROVIDER_ID,
            "provider_name": PROVIDER_NAME,
            "name": service_name,
            "category": enrichment.get("category"),
            "description": enrichment.get("description"),
            "tech_stack_tags": enrichment.get("tech_stack_tags", []),
            "use_case_tags": enrichment.get("use_case_tags", []),
            "is_152fz_compliant": is_152,
            "compliance_tags": compliance_tags,
            "compliance_note": compliance_note,
            "regions": regions,
            "pools": pools,
            "pricing_model": "pay-as-you-go",
            "price_from_rub": cheapest.get("price_rub") if cheapest else None,
            "price_from_value": cheapest.get("price_value") if cheapest else None,
            "price_unit": cheapest.get("price_unit") if cheapest else None,
            "support_level": None,
            "service_url": PRICING_URL,
            "source_url": PRICING_URL,
            "availability_source_url": AVAILABILITY_URL,
            "compliance_source_url": COMPLIANCE_URL,
            "pricing_items_count": len(items),
            "parsed_at": utc_now_iso(),
            "is_synthetic": False,
        })

    save_json(NORMALIZED_DIR / "services.json", services)
    save_json(NORMALIZED_DIR / "llm_errors.json", llm_errors)
    return services


if __name__ == "__main__":
    normalize_services()
