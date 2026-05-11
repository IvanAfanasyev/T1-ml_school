from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import selectel_config

_cfg = selectel_config()
PROVIDER_ID = _cfg.PROVIDER_ID
PROVIDER_NAME = _cfg.PROVIDER_NAME
BASE_PLATFORM = _cfg.BASE_PLATFORM
COMPLIANCE_URL = _cfg.COMPLIANCE_URL
AVAILABILITY_URL = _cfg.AVAILABILITY_URL
PRICING_URL = _cfg.PRICING_URL
DOCS_URL = _cfg.DOCS_URL
RAW_DIR = _cfg.RAW_DIR
NORMALIZED_DIR = _cfg.NORMALIZED_DIR

from app.utils import clean_text, soup_from_url, save_json, utc_now_iso


def parse_compliance() -> dict[str, Any]:
    soup = soup_from_url(COMPLIANCE_URL)
    text = clean_text(soup.get_text(" ", strip=True))
    low = text.lower()

    is_152fz = "152-фз" in low or "152 фз" in low or "№ 152-фз" in low or "федерального закона № 152" in low
    has_uz1 = "уз-1" in low or "первого уровня защищенности" in low or "1 уровень защищенности" in low
    has_acod = "а-цод" in low or "аттестованный сегмент цод" in low

    document_links = []
    for a in soup.find_all("a", href=True):
        label = clean_text(a.get_text(" ", strip=True))
        href = a["href"].strip()
        if href.startswith("/"):
            href = "https://docs.selectel.ru" + href
        if "files.selectel.ru" in href or "slc.tl" in href or label:
            document_links.append({"label": label, "url": href})

    result = {
        "provider_id": PROVIDER_ID,
        "source_url": COMPLIANCE_URL,
        "is_152fz_compliant": bool(is_152fz and has_uz1),
        "compliance_tags": [tag for tag, ok in [
            ("152-FZ", is_152fz),
            ("UZ-1", has_uz1),
            ("A-COD", has_acod),
        ] if ok],
        "compliance_note": (
            "Selectel предоставляет А-ЦОД — аттестованный сегмент ЦОД. "
            "Страница документов указывает, что А-ЦОД соответствует требованиям 152-ФЗ "
            "и позволяет хранить и обрабатывать персональные данные до УЗ-1."
        ),
        "document_links": document_links,
        "raw_text_preview": text[:3000],
        "parsed_at": utc_now_iso(),
    }
    return result


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

    compliance = parse_compliance()
    save_json(RAW_DIR / "compliance_raw.json", compliance)

    provider = {
        "provider_id": PROVIDER_ID,
        "name": PROVIDER_NAME,
        "base_platform": BASE_PLATFORM,
        "is_152fz_compliant": compliance["is_152fz_compliant"],
        "regions": ["Санкт-Петербург", "Москва", "Новосибирск"],
        "foreign_regions": ["Ташкент", "Алматы", "Найроби"],
        "availability_zones": [],
        "compliance_tags": compliance["compliance_tags"],
        "compliance_note": compliance["compliance_note"],
        "compliance_source_url": COMPLIANCE_URL,
        "availability_source_url": AVAILABILITY_URL,
        "pricing_url": PRICING_URL,
        "api_docs_url": DOCS_URL,
        "source_url": COMPLIANCE_URL,
        "parsed_at": utc_now_iso(),
    }
    save_json(NORMALIZED_DIR / "providers.json", [provider])


if __name__ == "__main__":
    main()
