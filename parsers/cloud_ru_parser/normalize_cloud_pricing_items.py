from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import cloud_ru_config

_cfg = cloud_ru_config()
NORMALIZED_DIR = _cfg.NORMALIZED_DIR
PROVIDER_ID = _cfg.PROVIDER_ID
RAW_DIR = _cfg.RAW_DIR

from app.utils import clean_text, load_json, normalize_billing_period, normalize_price, normalize_unit, save_json, slugify
from llm_enrichment import enrich_pricing_item_rule_based

# item_name значения, которые являются мусором (заголовки, сноски, навигация)
_GARBAGE_ITEM_NAMES = {"примечание", "nan", "наименование работ, услуг", "наименование"}

# подстроки в любом поле строки, указывающие на навигацию/пагинацию страницы
_NAVIGATION_TOKENS = {"следующая статья", "предыдущая статья", "rows volume:"}


def _is_garbage_row(row: dict) -> bool:
    item_name = clean_text(row.get("item_name", "")).lower()
    if not item_name:
        return True
    if item_name in _GARBAGE_ITEM_NAMES:
        return True
    # строка из одного-двух чисел — артефакт смещения текстового парсера
    if re.fullmatch(r"\d{1,3}", item_name):
        return True
    # любое поле строки содержит навигационный токен
    all_text = " ".join(clean_text(str(v)).lower() for v in row.values())
    return any(token in all_text for token in _NAVIGATION_TOKENS)


def normalize_pricing_items() -> list[dict]:
    pages = load_json(RAW_DIR / "tariff_pages_raw.json", [])
    items = []

    for page in pages:
        service_name = page.get("service_name") or page.get("input_service_name") or "unknown"
        service_id = f"{PROVIDER_ID}-{slugify(service_name)}"
        source_url = page.get("tariff_url")
        for idx, row in enumerate(page.get("rows", []), start=1):
            if _is_garbage_row(row):
                continue
            item_name = clean_text(row.get("item_name"))
            if not item_name:
                continue
            period = normalize_billing_period(row.get("tariff_period", ""))
            unit = normalize_unit(row.get("tariff_unit", ""), period)
            price_without_vat = normalize_price(row.get("price_without_vat_raw"))
            price_with_vat = normalize_price(row.get("price_with_vat_raw"))
            enrichment = enrich_pricing_item_rule_based(item_name, service_name)
            raw_text = " | ".join([clean_text(v) for v in row.values() if clean_text(v)])

            items.append({
                "pricing_item_id": f"{service_id}-{idx:04d}",
                "service_id": service_id,
                "provider_id": PROVIDER_ID,
                "item_name": item_name,
                "item_type": enrichment["item_type"],
                "price_rub": price_with_vat if price_with_vat is not None else price_without_vat,
                "price_without_vat_rub": price_without_vat,
                "price_with_vat_rub": price_with_vat,
                "price_unit": unit,
                "billing_period": period,
                "region": "ru-moscow-1",
                "configuration_tags": enrichment["configuration_tags"],
                "source_url": source_url,
                "source_pdf_url": page.get("pdf_url"),
                "raw_text": raw_text,
                "parsed_at": page.get("parsed_at"),
                "is_synthetic": False,
            })
    return items


def main() -> None:
    items = normalize_pricing_items()
    save_json(NORMALIZED_DIR / "service_pricing_items.json", items)
    print(f"Saved {len(items)} pricing items: {NORMALIZED_DIR / 'service_pricing_items.json'}")


if __name__ == "__main__":
    main()
