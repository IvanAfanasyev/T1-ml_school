from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import selectel_config

_cfg = selectel_config()
PROVIDER_ID = _cfg.PROVIDER_ID
AVAILABILITY_URL = _cfg.AVAILABILITY_URL
RAW_DIR = _cfg.RAW_DIR
NORMALIZED_DIR = _cfg.NORMALIZED_DIR

from app.utils import clean_text, soup_from_url, save_json, utc_now_iso, lines_from_element, slugify

RUSSIAN_REGIONS = ["Санкт-Петербург", "Москва", "Новосибирск"]
FOREIGN_REGIONS = ["Ташкент", "Алматы", "Найроби"]
KNOWN_REGIONS = RUSSIAN_REGIONS + FOREIGN_REGIONS

POOL_RE = re.compile(r"\b(?:SPB|MSK|NSK|TAS|ALM|NBO)-\d\b|\bru-\d+[a-z]?\b|\buz-\d+[a-z]?\b|\bkz-\d+[a-z]?\b|\bke-\d+[a-z]?\b|\bgis-\d+[a-z]?\b", re.IGNORECASE)


def _get_h2_sections(soup: BeautifulSoup) -> list[tuple[str, list[Tag]]]:
    sections: list[tuple[str, list[Tag]]] = []
    for h2 in soup.find_all("h2"):
        title = clean_text(h2.get_text(" ", strip=True))
        nodes: list[Tag] = []
        for sib in h2.find_next_siblings():
            if getattr(sib, "name", None) == "h2":
                break
            if isinstance(sib, Tag):
                nodes.append(sib)
        if title:
            sections.append((title, nodes))
    return sections


def _extract_lines(nodes: list[Tag]) -> list[str]:
    lines: list[str] = []
    for node in nodes:
        lines.extend(lines_from_element(node))
    # remove exact duplicated consecutive lines
    out = []
    for line in lines:
        if not out or out[-1] != line:
            out.append(line)
    return out


def _regions_in_lines(lines: list[str]) -> list[str]:
    joined = "\n".join(lines)
    return [r for r in KNOWN_REGIONS if r in joined]


def _pools_in_lines(lines: list[str]) -> list[str]:
    found = []
    for line in lines:
        for m in POOL_RE.findall(line):
            val = m.upper() if re.match(r"^(SPB|MSK|NSK|TAS|ALM|NBO)-", m, re.I) else m.lower()
            if val not in found:
                found.append(val)
    return found


def _detect_certified(service_name: str, lines: list[str]) -> bool:
    text = (service_name + "\n" + "\n".join(lines)).lower()
    return any(x in text for x in ["а-цод", "аттестованный сегмент", "аттестованное облако", "gis-"])


def parse_availability() -> list[dict[str, Any]]:
    soup = soup_from_url(AVAILABILITY_URL)
    sections = _get_h2_sections(soup)
    items: list[dict[str, Any]] = []

    for title, nodes in sections:
        lines = _extract_lines(nodes)
        if not lines:
            continue
        regions = _regions_in_lines(lines)
        pools = _pools_in_lines(lines)
        certified = _detect_certified(title, lines)
        text = "\n".join(lines)

        service_id = f"{PROVIDER_ID}-{slugify(title)}"
        items.append({
            "provider_id": PROVIDER_ID,
            "service_id": service_id,
            "service_name": title,
            "regions": [r for r in regions if r in RUSSIAN_REGIONS],
            "foreign_regions": [r for r in regions if r in FOREIGN_REGIONS],
            "pools": pools,
            "is_certified_segment_available": certified,
            "compliance_tags": ["152-FZ", "UZ-1"] if certified else [],
            "source_url": AVAILABILITY_URL,
            "raw_text_preview": text[:5000],
            "parsed_at": utc_now_iso(),
        })

    return items


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

    availability = parse_availability()
    save_json(RAW_DIR / "availability_raw.json", availability)
    save_json(NORMALIZED_DIR / "service_availability.json", availability)


if __name__ == "__main__":
    main()
