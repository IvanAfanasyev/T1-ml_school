from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import selectel_config

_cfg = selectel_config()
PROVIDER_ID = _cfg.PROVIDER_ID
RAW_DIR = _cfg.RAW_DIR
NORMALIZED_DIR = _cfg.NORMALIZED_DIR
PRICING_URL = _cfg.PRICING_URL

from app.utils import load_json, save_json, slugify, clean_text, utc_now_iso

ON_REQUEST_WORDS = ["по запросу", "индивидуально", "уточняйте", "договорная"]


def parse_money(text: str | None) -> float | None:
    if text is None:
        return None
    s = clean_text(text)
    low = s.lower()
    if "бесплатно" in low:
        return 0.0
    if any(w in low for w in ON_REQUEST_WORDS):
        return None

    # Prefer numbers before ₽.
    matches = re.findall(r"(\d[\d\s]*[.,]?\d*)\s*₽", s)
    if matches:
        raw = matches[-1].replace(" ", "").replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            return None

    nums = re.findall(r"\d+(?:[\s]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?", s)
    if not nums:
        return None
    raw = nums[-1].replace(" ", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def choose_price(price_fields: dict[str, str]) -> tuple[float | None, str | None, str | None, str | None]:
    # Prefer monthly price, then general VAT price, then hourly, then any price.
    priority = [
        "Цена в месяц",
        "Цена с НДС",
        "Цена",
        "Цена в час",
        "Справочная стоимость с НДС",
    ]
    normalized = {clean_text(k).replace("\u00a0", " "): v for k, v in price_fields.items()}
    for key in priority:
        if key in normalized:
            price = parse_money(normalized[key])
            if price is not None:
                period = label_to_period(key, normalized[key])
                unit = make_price_unit(key, normalized[key], period)
                return price, unit, period, key
    return None, None, None, None


def label_to_period(label: str, value: str) -> str:
    text = f"{label} {value}".lower()
    if "час" in text:
        return "hour"
    if "мес" in text or "месяц" in text:
        return "month"
    if "гб" in text or "gb" in text:
        return "unit"
    return "unit"


def make_price_unit(label: str, value: str, period: str) -> str:
    v = clean_text(value).lower()
    # Try suffix after ₽: "1,43 ₽/ГБ в мес." -> "руб/ГБ в мес."
    m = re.search(r"₽\s*/\s*([^\s].*)$", clean_text(value))
    if m:
        return "руб/" + clean_text(m.group(1))
    if period == "hour":
        return "руб/час"
    if period == "month":
        return "руб/мес"
    return "руб/ед"


def infer_billing_value(item_name: str, price_unit: str | None) -> str | None:
    text = clean_text(item_name)
    # common: "..., 1 ГБ", "за 1 ГБ", "1 шт", "Ядра"
    patterns = [
        r"(?:за\s*)?(1\s*(?:ГБ|Гб|GB|МБ|MB|ТБ|TB|шт\.?|ядро|ядра|vCPU))",
        r"(\d+\s*(?:ГБ|Гб|GB|МБ|MB|ТБ|TB|шт\.?|ядро|ядра|vCPU))",
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return clean_text(m.group(1))
    if price_unit and "/гб" in price_unit.lower():
        return "1 ГБ"
    return None


def infer_item_type(service_name: str, item_name: str) -> str:
    s = f"{service_name} {item_name}".lower()
    if any(x in s for x in ["s3", "хранили", "диск", "snapshot", "снапшот", "backup", "бэкап", "репозитор"]):
        return "storage"
    if any(x in s for x in ["postgres", "mysql", "redis", "dbaas", "clickhouse", "база", "database"]):
        return "database"
    if any(x in s for x in ["kubernetes", "container", "registry", "контейнер"]):
        return "container"
    if any(x in s for x in ["ip", "подсеть", "трафик", "direct", "порт", "балансировщик", "firewall", "межсет"]):
        return "network"
    if any(x in s for x in ["gpu", "vcpu", "cpu", "ram", "сервер", "vm", "vdc"]):
        return "compute"
    if any(x in s for x in ["защит", "ddos", "usergate", "waf", "сертифицирован"]):
        return "security"
    return "other"


def _build_configuration_tags(item_name: str, item_type: str, context: dict) -> list[str]:
    tags: set[str] = {item_type}
    text = item_name.lower()
    for token in ["ssd", "hdd", "nvme", "gpu", "cpu", "ram", "ipv4", "ipv6",
                  "s3", "nfs", "iscsi", "backup", "snapshot", "cdn"]:
        if token in text:
            tags.add(token)
    for kw, tag in [("гб", "gb"), ("тб", "tb"), ("vcpu", "vcpu"), ("ядр", "cpu-core")]:
        if kw in text:
            tags.add(tag)
    storage_class = context.get("storage_class")
    if storage_class:
        tags.add(storage_class.lower())
    disk_type = context.get("disk_type")
    if disk_type:
        tags.add(disk_type.lower())
    return sorted(tags)


def normalize() -> list[dict[str, Any]]:
    raw = load_json(RAW_DIR / "prices_raw.json", {})
    rows = raw.get("rows", []) if isinstance(raw, dict) else []

    items: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    counters: dict[str, int] = {}
    for row in rows:
        service_name = row.get("service_name", "Cloud Service")
        service_id = row.get("service_id") or f"{PROVIDER_ID}-{slugify(service_name)}"
        counters[service_id] = counters.get(service_id, 0) + 1
        idx = counters[service_id]

        price, price_unit, billing_period, selected_label = choose_price(row.get("price_fields", {}))
        price_on_request = price is None and any(w in row.get("raw_text", "").lower() for w in ON_REQUEST_WORDS)
        if price is None and not price_on_request:
            skipped.append({"reason": "no_price", "row": row})
            continue

        item_name = clean_text(row.get("item_name"))
        billing_value = infer_billing_value(item_name, price_unit)
        context = row.get("context") or {}

        item_type = infer_item_type(service_name, item_name)
        item = {
            "pricing_item_id": f"{service_id}-{idx:04d}",
            "service_id": service_id,
            "provider_id": PROVIDER_ID,
            "service_name": service_name,
            "item_name": item_name,
            "item_type": item_type,
            "price_rub": price,
            "price_value": price,
            "price_currency": "руб",
            "price_unit": price_unit,
            "billing_value": billing_value,
            "billing_period": billing_period,
            "price_on_request": price_on_request,
            "region": context.get("region") or context.get("city"),
            "pool": context.get("pool"),
            "configuration_tags": _build_configuration_tags(item_name, item_type, context),
            "context": context,
            "selected_price_label": selected_label,
            "source_url": row.get("source_url") or PRICING_URL,
            "raw_text": row.get("raw_text"),
            "parsed_at": utc_now_iso(),
            "is_synthetic": False,
        }
        items.append(item)

    save_json(NORMALIZED_DIR / "service_pricing_items.json", items)
    save_json(NORMALIZED_DIR / "pricing_items_stats.json", {
        "pricing_items_count": len(items),
        "skipped_rows_count": len(skipped),
        "price_on_request_count": sum(1 for x in items if x["price_on_request"]),
        "parsed_at": utc_now_iso(),
    })
    save_json(RAW_DIR / "pricing_skipped_rows.json", skipped[:500])
    return items


if __name__ == "__main__":
    normalize()
