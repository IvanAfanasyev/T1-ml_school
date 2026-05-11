from __future__ import annotations

import re
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

from app.utils import load_json, save_json, slugify, clean_text
from llm_enrichment import enrich_pricing_item_rule_based


HEADER_WORDS = {
    "параметр",
    "значение",
    "цена за минуту",
    "цена за 30 дней",
    "в том числе ндс",
}

ON_REQUEST_WORDS = (
    "по запросу",
    "расчет стоимости по запросу",
    "расчёт стоимости по запросу",
    "по запросу клиента",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_money(text: str) -> float | None:
    if text is None:
        return None

    s = str(text).replace("\xa0", " ")
    if any(w in s.lower() for w in ON_REQUEST_WORDS):
        return None

    # strip discount markers (-50%, +20%) so they don't interfere
    s = re.sub(r"[-+]?\s*\d+\s*%", "", s)

    # find all prices attached to ₽: numbers like "174 867" or "2,02" before ₽
    # pattern: 1-3 digits, optionally followed by groups of exactly 3 digits separated by space
    prices = re.findall(r"(\d{1,3}(?:\s\d{3})*(?:[,.]\d+)?)\s*₽", s)
    if prices:
        # last price = discounted price when there's a sale ("174 867 ₽ 87 433 ₽")
        raw = prices[-1].replace(" ", "").replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            pass

    # fallback for "руб" instead of ₽
    s2 = re.sub(r"руб\.?", "₽", s)
    prices2 = re.findall(r"(\d{1,3}(?:\s\d{3})*(?:[,.]\d+)?)\s*₽", s2)
    if prices2:
        raw = prices2[-1].replace(" ", "").replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            pass

    return None


def _is_header_row(cells: list[str]) -> bool:
    joined = " ".join(cells).lower()
    return (
        "параметр" in joined
        and "значение" in joined
        and ("цена" in joined or "30 дней" in joined)
    )


def _is_invalid_row(cells: list[str]) -> bool:
    if len(cells) < 2:
        return True

    joined = " ".join(cells).lower()
    first = cells[0].strip().lower()

    if _is_header_row(cells):
        return True

    if first in HEADER_WORDS:
        return True

    if "cookie" in joined or "javascript" in joined:
        return True

    if "итого" == first:
        return True

    return False


def _extract_row_fields(cells: list[str]) -> dict[str, Any] | None:
    """
    VK Cloud pricelist rows usually look like:
    Параметр | Значение | Цена за минуту | Цена за 30 дней

    Sometimes:
    Параметр | Значение | Цена за 30 дней

    We prefer the 30-day/month price for MVP budget comparison.
    """
    if _is_invalid_row(cells):
        return None

    item_name = clean_text(cells[0])
    billing_value = clean_text(cells[1]) if len(cells) > 1 else ""

    price_per_minute = None
    price_per_month = None

    if len(cells) >= 4:
        price_per_minute = parse_money(cells[2])
        price_per_month = parse_money(cells[3])
    elif len(cells) == 3:
        # Usually monthly only, e.g. MS SQL | 1 шт. ... | 32 307 ₽
        price_per_month = parse_money(cells[2])
    else:
        return None

    row_text = " | ".join(cells)
    price_on_request = any(w in row_text.lower() for w in ON_REQUEST_WORDS)

    # Prefer monthly price because it is easier for ranking by user budget.
    if price_per_month is not None:
        price_rub = price_per_month
        billing_period = "month"
        unit_suffix = "мес"
    elif price_per_minute is not None:
        price_rub = price_per_minute
        billing_period = "minute"
        unit_suffix = "мин"
    elif price_on_request:
        price_rub = None
        billing_period = "request"
        unit_suffix = "запрос"
    else:
        return None

    # Do not accidentally take "1 ГБ" / "1 шт" as price.
    # Valid price must come from actual price columns, not billing_value.
    unit = billing_value or "unit"
    price_unit = f"руб/{unit}/{unit_suffix}"

    return {
        "item_name": item_name,
        "billing_value": billing_value,
        "price_rub": price_rub,
        "price_value": price_rub,
        "price_currency": "руб",
        "price_unit": price_unit,
        "billing_period": billing_period,
        "price_on_request": price_on_request,
        "raw_text": row_text,
    }


def main() -> None:
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

    raw = load_json(RAW_DIR / "pricelist_raw.json")
    services = raw.get("services", [])

    items: list[dict[str, Any]] = []
    skipped = 0
    on_request = 0

    for service in services:
        service_id = service["service_id"]
        service_name = service["service_name"]
        idx = 1

        for table in service.get("tables", []):
            for cells in table.get("rows", []):
                fields = _extract_row_fields(cells)
                if fields is None:
                    skipped += 1
                    continue

                enrichment = enrich_pricing_item_rule_based(fields["item_name"], service_name)
                if fields.get("price_on_request"):
                    on_request += 1

                item = {
                    "pricing_item_id": f"{service_id}-{idx:04d}",
                    "service_id": service_id,
                    "provider_id": PROVIDER_ID,
                    "item_name": fields["item_name"],
                    "item_type": enrichment["item_type"],
                    "price_rub": fields["price_rub"],
                    "price_value": fields["price_value"],
                    "price_currency": fields["price_currency"],
                    "price_unit": fields["price_unit"],
                    "billing_value": fields["billing_value"],
                    "billing_period": fields["billing_period"],
                    "price_on_request": fields["price_on_request"],
                    "region": None,
                    "configuration_tags": enrichment["configuration_tags"],
                    "source_url": PRICING_URL,
                    "raw_text": fields["raw_text"],
                    "parsed_at": _utc_now(),
                    "is_synthetic": False,
                }
                items.append(item)
                idx += 1

    save_json(NORMALIZED_DIR / "service_pricing_items.json", items)
    save_json(NORMALIZED_DIR / "pricing_items_stats.json", {
        "pricing_items_count": len(items),
        "skipped_rows_count": skipped,
        "price_on_request_count": on_request,
        "parsed_at": _utc_now(),
    })


if __name__ == "__main__":
    main()
