from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import vk_cloud_config

_cfg = vk_cloud_config()
PRICING_URL = _cfg.PRICELIST_URL
RAW_DIR = _cfg.RAW_DIR

from app.utils import fetch, clean_text, save_json, slugify


PRICE_WORDS = ("₽", "руб", "р.", "стоимости", "цена")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _looks_like_service_heading(text: str) -> bool:
    text = clean_text(text)
    if not text:
        return False
    bad = {
        "тарифы", "стоимость", "прайс-лист", "навигация", "содержание",
        "параметр", "значение", "цена за минуту", "цена за 30 дней",
    }
    low = text.lower()
    if low in bad:
        return False
    if len(text) > 120:
        return False
    return True


def _nearest_heading(table: Tag) -> str:
    # Walk backwards and find a meaningful heading before this table.
    cur = table
    while cur:
        cur = cur.find_previous(["h1", "h2", "h3", "h4"])
        if not cur:
            break
        title = clean_text(cur.get_text(" ", strip=True))
        if _looks_like_service_heading(title):
            return title
    return "VK Cloud Service"


def _table_rows(table: Tag) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = [clean_text(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if cells:
            rows.append(cells)
    return rows


def _is_pricing_table(rows: list[list[str]]) -> bool:
    if not rows:
        return False
    joined = " ".join(" ".join(r) for r in rows[:3]).lower()
    return (
        ("цена" in joined or "₽" in joined or "руб" in joined)
        and ("параметр" in joined or "значение" in joined or "30 дней" in joined or "минут" in joined)
    )


def _normalize_service_name(name: str) -> str:
    return clean_text(name).replace("**", "").strip()


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    html = fetch(PRICING_URL)
    soup = BeautifulSoup(html, "lxml")

    services: dict[str, dict[str, Any]] = {}
    skipped_tables = 0

    for table in soup.find_all("table"):
        rows = _table_rows(table)
        if not _is_pricing_table(rows):
            skipped_tables += 1
            continue

        service_name = _normalize_service_name(_nearest_heading(table))
        service_id = f"vk-cloud-{slugify(service_name)}"

        if service_id not in services:
            services[service_id] = {
                "service_id": service_id,
                "service_name": service_name,
                "source_url": PRICING_URL,
                "tables": [],
            }

        services[service_id]["tables"].append({
            "rows": rows,
            "raw_text": clean_text(table.get_text(" | ", strip=True)),
        })

    result = {
        "provider_id": "vk-cloud",
        "source_url": PRICING_URL,
        "services": list(services.values()),
        "services_count": len(services),
        "skipped_tables": skipped_tables,
        "parsed_at": _utc_now(),
    }

    save_json(RAW_DIR / "pricelist_raw.json", result)


if __name__ == "__main__":
    main()
