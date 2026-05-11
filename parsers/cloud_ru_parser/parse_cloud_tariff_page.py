from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import cloud_ru_config

_cfg = cloud_ru_config()
RAW_DIR = _cfg.RAW_DIR

from app.utils import (
    absolute_url,
    clean_text,
    extract_service_name_from_title,
    fetch,
    load_json,
    now_iso,
    save_json,
    soup_from_html,
)


def find_pdf_url(soup, page_url: str) -> str | None:
    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(" ")).lower()
        href = a["href"]
        if "pdf" in text or href.lower().endswith(".pdf"):
            return absolute_url(page_url, href)
    return None


def normalize_columns(columns: list[Any]) -> list[str]:
    result = []
    for col in columns:
        name = clean_text(col).lower()
        if name in {"№", "no", "номер"} or name.startswith("№"):
            result.append("number")
        elif "наименование" in name:
            result.append("item_name")
        elif "единица" in name:
            result.append("tariff_unit")
        elif "период" in name:
            result.append("tariff_period")
        elif "без ндс" in name:
            result.append("price_without_vat_raw")
        elif "ндс" in name and "без" not in name and "цена" not in name:
            result.append("vat_raw")
        elif "с ндс" in name:
            result.append("price_with_vat_raw")
        else:
            result.append(name or "unknown")
    return result


def parse_tables_with_pandas(html: str) -> list[dict]:
    tables = pd.read_html(html)
    rows: list[dict] = []
    for table in tables:
        table = table.dropna(how="all")
        if table.empty:
            continue
        table.columns = normalize_columns(list(table.columns))
        if "item_name" not in table.columns:
            continue
        for _, row in table.iterrows():
            item_name = clean_text(row.get("item_name"))
            if not item_name or item_name.lower() in {"nan", "наименование работ, услуг"}:
                continue
            rows.append({k: clean_text(v) for k, v in row.to_dict().items()})
    return rows


def parse_tables_from_text(soup) -> list[dict]:
    """Fallback for rendered docs where table rows are linearized in text."""
    text_items = [clean_text(x) for x in soup.get_text("\n").split("\n")]
    text_items = [x for x in text_items if x]
    rows: list[dict] = []

    start = None
    for i, value in enumerate(text_items):
        if value == "№" and i + 5 < len(text_items) and "Наименование" in text_items[i + 1]:
            start = i + 7
            break
    if start is None:
        return rows

    i = start
    while i + 5 < len(text_items):
        number = text_items[i]
        if not re.match(r"^\d+\.?$", number):
            i += 1
            continue
        item_name = text_items[i + 1]
        tariff_unit = text_items[i + 2]
        tariff_period = text_items[i + 3]
        price_without_vat_raw = text_items[i + 4]
        vat_raw = text_items[i + 5]
        price_with_vat_raw = text_items[i + 6] if i + 6 < len(text_items) else ""

        if not re.search(r"\d", price_without_vat_raw):
            i += 1
            continue

        rows.append({
            "number": number.rstrip("."),
            "item_name": item_name,
            "tariff_unit": tariff_unit,
            "tariff_period": tariff_period,
            "price_without_vat_raw": price_without_vat_raw,
            "vat_raw": vat_raw,
            "price_with_vat_raw": price_with_vat_raw,
        })
        i += 7
    return rows


def parse_tariff_page(service_name: str, page_url: str) -> dict:
    html = fetch(page_url)
    soup = soup_from_html(html)
    h1 = clean_text(soup.find("h1").get_text(" ")) if soup.find("h1") else ""
    parsed_service_name = extract_service_name_from_title(h1) or service_name
    pdf_url = find_pdf_url(soup, page_url)

    try:
        rows = parse_tables_with_pandas(html)
    except Exception:
        rows = []
    if not rows:
        rows = parse_tables_from_text(soup)

    return {
        "service_name": parsed_service_name,
        "input_service_name": service_name,
        "tariff_url": page_url,
        "pdf_url": pdf_url,
        "title": h1,
        "rows": rows,
        "rows_count": len(rows),
        "parsed_at": now_iso(),
    }


def main() -> None:
    index = load_json(RAW_DIR / "tariff_index_raw.json", [])
    if not index:
        raise SystemExit("Run parse_cloud_tariffs_index.py first")

    pages = []
    for item in index:
        print(f"Parsing: {item['service_name']}")
        try:
            pages.append(parse_tariff_page(item["service_name"], item["tariff_url"]))
        except Exception as exc:
            pages.append({
                "service_name": item["service_name"],
                "tariff_url": item["tariff_url"],
                "error": str(exc),
                "rows": [],
                "rows_count": 0,
                "parsed_at": now_iso(),
            })
    save_json(RAW_DIR / "tariff_pages_raw.json", pages)
    print(f"Saved: {RAW_DIR / 'tariff_pages_raw.json'}")


if __name__ == "__main__":
    main()
