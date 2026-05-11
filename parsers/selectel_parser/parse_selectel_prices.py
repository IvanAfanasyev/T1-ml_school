from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import selectel_config

_cfg = selectel_config()
PROVIDER_ID = _cfg.PROVIDER_ID
PRICING_URL = _cfg.PRICING_URL
RAW_DIR = _cfg.RAW_DIR

from app.utils import clean_text, soup_from_url, save_json, utc_now_iso, lines_from_element, slugify

PRICE_LABELS = {
    "Цена в час",
    "Цена в месяц",
    "Цена",
    "Цена с НДС",
    "Справочная стоимость с НДС",
}

CONTEXT_LABELS = {
    "Регион",
    "Пул",
    "Тип VDC",
    "Класс хранилища",
    "Модель оплаты",
    "Наличие GPU",
    "Период",
    "Город",
    "Локация",
    "Тип сервера",
    "Тип диска",
}

ITEM_LABELS = {
    "Наименование",
    "Конфигурация",
}

# Headings that are normally present on https://selectel.ru/prices/.
# They are used as a fallback when the HTML structure is flattened.
KNOWN_SERVICE_HEADINGS = [
    "Выделенные серверы",
    "Дополнительные услуги к выделенным серверам",
    "Облачные серверы",
    "Серверы с GPU",
    "S3",
    "Облачные базы данных",
    "Managed Kubernetes",
    "Container Registry",
    "Публичное облако на базе VMware",
    "Приватное облако на базе VMware",
    "Размещение оборудования",
    "Сетевые услуги",
    "CDN",
    "Direct Connect",
    "Защита от DDoS",
    "Средства защиты информации",
    "Межсетевые экраны",
    "Балансировщик нагрузки",
    "Резервное копирование в облаке",
    "Кибер Бэкап Облачный",
    "Файловое хранилище",
    "Сетевые диски",
    "SSL-сертификаты",
    "Домены .RU и .РФ",
    "Приватный DNS",
    "DNS-хостинг",
]

STOP_LABELS = PRICE_LABELS | CONTEXT_LABELS | ITEM_LABELS | {
    "Актуализация цен...",
    "Цена всех услуг указана с учетом НДС 22%",
    "Заказать в панели",
    "Рассчитать стоимость",
}


def _normalize_label(s: str) -> str:
    return clean_text(s).replace("\u00a0", " ").replace("\u202f", " ")


def _get_h2_sections(soup: BeautifulSoup) -> list[tuple[str, list[Tag]]]:
    sections: list[tuple[str, list[Tag]]] = []
    for h2 in soup.find_all(["h2", "h3"]):
        title = clean_text(h2.get_text(" ", strip=True))
        if title not in KNOWN_SERVICE_HEADINGS and not _looks_like_price_service_title(title):
            continue
        nodes: list[Tag] = []
        for sib in h2.find_next_siblings():
            if getattr(sib, "name", None) in {"h2", "h3"}:
                break
            if isinstance(sib, Tag):
                nodes.append(sib)
        if title:
            sections.append((title, nodes))
    return sections


def _looks_like_price_service_title(title: str) -> bool:
    t = clean_text(title)
    if len(t) < 3 or len(t) > 90:
        return False
    bad = ["Продукты", "Популярные", "AI/ML", "Серверы и вычисления", "Хранение", "Базы данных", "Kubernetes", "VMware", "Безопасность", "Организация сети", "Домены", "Управление"]
    return not any(t == x or t.startswith(x) for x in bad)


def _all_lines(soup: BeautifulSoup) -> list[str]:
    root = soup.body or soup
    lines = lines_from_element(root)
    out: list[str] = []
    for line in lines:
        line = _normalize_label(line)
        if line and (not out or out[-1] != line):
            out.append(line)
    return out


def _extract_lines(nodes: list[Tag]) -> list[str]:
    lines: list[str] = []
    for node in nodes:
        lines.extend(lines_from_element(node))
    out: list[str] = []
    for line in lines:
        line = _normalize_label(line)
        if line and (not out or out[-1] != line):
            out.append(line)
    return out


def _next_value(lines: list[str], idx: int) -> str | None:
    j = idx + 1
    while j < len(lines):
        val = _normalize_label(lines[j])
        if val:
            return val
        j += 1
    return None


def _is_bad_item_name(name: str) -> bool:
    n = _normalize_label(name)
    low = n.lower()
    return (
        not n
        or n in STOP_LABELS
        or low.startswith("цена всех услуг")
        or low.startswith("актуализация")
        or low == "success"
        or low.startswith("заказать")
        or len(n) > 250
    )


def _parse_section(service_name: str, lines: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    context: dict[str, str | None] = {
        "region": None,
        "pool": None,
        "vdc_type": None,
        "storage_class": None,
        "payment_model": None,
        "gpu_presence": None,
        "period": None,
        "city": None,
        "location": None,
        "server_type": None,
        "disk_type": None,
    }

    label_to_key = {
        "Регион": "region",
        "Пул": "pool",
        "Тип VDC": "vdc_type",
        "Класс хранилища": "storage_class",
        "Модель оплаты": "payment_model",
        "Наличие GPU": "gpu_presence",
        "Период": "period",
        "Город": "city",
        "Локация": "location",
        "Тип сервера": "server_type",
        "Тип диска": "disk_type",
    }

    i = 0
    while i < len(lines):
        line = _normalize_label(lines[i])

        if line in label_to_key:
            val = _next_value(lines, i)
            if val and val not in STOP_LABELS and not _is_bad_item_name(val):
                context[label_to_key[line]] = val
            i += 2
            continue

        if line in ITEM_LABELS:
            item_label = line
            name = _next_value(lines, i)
            if not name or _is_bad_item_name(name):
                i += 1
                continue

            price_fields: dict[str, str] = {}
            extra_fields: dict[str, str] = {}
            j = i + 2
            while j < len(lines):
                cur = _normalize_label(lines[j])

                if cur in ITEM_LABELS:
                    break
                if cur in label_to_key:
                    # New region/pool context starts; next item belongs to another context.
                    break
                if cur in KNOWN_SERVICE_HEADINGS and cur != service_name:
                    break
                if cur in PRICE_LABELS:
                    val = _next_value(lines, j)
                    if val and val not in STOP_LABELS:
                        price_fields[cur] = val
                    j += 2
                    continue
                # Dedicated servers use Processor/Memory/Disks before Configuration.
                if cur in {"Процессор", "Память", "Диски"}:
                    val = _next_value(lines, j)
                    if val and val not in STOP_LABELS:
                        extra_fields[cur] = val
                    j += 2
                    continue
                if cur.lower().startswith("актуализация") or cur.lower().startswith("цена всех услуг"):
                    break
                j += 1

            if price_fields:
                raw_parts = [name]
                raw_parts.extend(f"{k}: {v}" for k, v in extra_fields.items())
                raw_parts.extend(f"{k}: {v}" for k, v in price_fields.items())
                rows.append({
                    "provider_id": PROVIDER_ID,
                    "service_name": service_name,
                    "service_id": f"{PROVIDER_ID}-{slugify(service_name)}",
                    "item_name": name,
                    "item_label": item_label,
                    "context": dict(context),
                    "extra_fields": extra_fields,
                    "price_fields": price_fields,
                    "source_url": PRICING_URL,
                    "raw_text": " | ".join(raw_parts),
                    "parsed_at": utc_now_iso(),
                })
            i = max(j, i + 1)
            continue

        i += 1

    return rows


def _parse_by_known_headings(lines: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    headings = set(KNOWN_SERVICE_HEADINGS)
    current_title: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal rows, current_title, buf
        if current_title and buf:
            section_rows = _parse_section(current_title, buf)
            rows.extend(section_rows)
        buf = []

    for line in lines:
        if line in headings:
            flush()
            current_title = line
            buf = []
        elif current_title:
            buf.append(line)
    flush()
    return rows


def parse_prices() -> list[dict[str, Any]]:
    soup = soup_from_url(PRICING_URL)
    result: list[dict[str, Any]] = []

    # First try real h2/h3 sections.
    for service_name, nodes in _get_h2_sections(soup):
        lines = _extract_lines(nodes)
        result.extend(_parse_section(service_name, lines))

    # Fallback: parse flattened text by known service headings.
    if not result:
        result = _parse_by_known_headings(_all_lines(soup))

    # Dedupe identical rows.
    seen = set()
    deduped = []
    for row in result:
        key = (row.get("service_name"), row.get("item_name"), tuple(sorted((row.get("price_fields") or {}).items())))
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    return deduped


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = parse_prices()
    save_json(RAW_DIR / "prices_raw.json", {
        "provider_id": PROVIDER_ID,
        "source_url": PRICING_URL,
        "rows_count": len(rows),
        "rows": rows,
        "parsed_at": utc_now_iso(),
    })


if __name__ == "__main__":
    main()
