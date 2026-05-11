from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import cloud_ru_config

_cfg = cloud_ru_config()
BASE_PLATFORM = _cfg.BASE_PLATFORM
COMPLIANCE_URL = _cfg.COMPLIANCE_URL
NORMALIZED_DIR = _cfg.NORMALIZED_DIR
PROVIDER_ID = _cfg.PROVIDER_ID
PROVIDER_NAME = _cfg.PROVIDER_NAME
RAW_DIR = _cfg.RAW_DIR
REGIONS_URL = _cfg.REGIONS_URL
TARIFF_INDEX_URL = _cfg.TARIFF_INDEX_URL

from app.utils import clean_text, fetch, now_iso, save_json, soup_from_html


def parse_compliance() -> dict:
    html = fetch(COMPLIANCE_URL)
    soup = soup_from_html(html)
    text = clean_text(soup.get_text(" "))

    tags = []
    if "152-ФЗ" in text or "152 ФЗ" in text:
        tags.append("152-FZ")
    if re.search(r"УЗ-?1", text, flags=re.IGNORECASE):
        tags.append("UZ-1")
    if "187-ФЗ" in text or "187 ФЗ" in text:
        tags.append("187-FZ")
    if "ФСТЭК" in text:
        tags.append("FSTEC")
    if "ISO/IEC 27001" in text:
        tags.append("ISO/IEC 27001")
    if "ISO/IEC 27017" in text:
        tags.append("ISO/IEC 27017")
    if "ISO/IEC 27018" in text:
        tags.append("ISO/IEC 27018")
    if "PCI DSS" in text:
        tags.append("PCI DSS")

    return {
        "source_url": COMPLIANCE_URL,
        "is_152fz_compliant": "152-FZ" in tags,
        "compliance_tags": sorted(set(tags)),
        "raw_text_excerpt": text[:3000],
        "parsed_at": now_iso(),
    }


def parse_regions() -> dict:
    html = fetch(REGIONS_URL)
    soup = soup_from_html(html)
    text = clean_text(soup.get_text(" "))

    region_match = re.search(r"одном регионе\s+—\s+([A-Za-zА-Яа-я-]+).*?идентификатор\s+—\s+([a-z0-9-]+)", text)
    region_name = region_match.group(1) if region_match else "RU-Moscow"
    region_id = region_match.group(2) if region_match else "ru-moscow-1"

    zones = sorted(set(re.findall(r"ru-moscow-1[a-z]", text)))

    return {
        "source_url": REGIONS_URL,
        "regions": ["Russia", region_name, region_id],
        "availability_zones": zones,
        "raw_text_excerpt": text[:3000],
        "parsed_at": now_iso(),
    }


def main() -> None:
    compliance = parse_compliance()
    regions = parse_regions()

    provider = {
        "provider_id": PROVIDER_ID,
        "name": PROVIDER_NAME,
        "base_platform": BASE_PLATFORM,
        "is_152fz_compliant": compliance["is_152fz_compliant"],
        "regions": regions["regions"],
        "availability_zones": regions["availability_zones"],
        "compliance_tags": compliance["compliance_tags"],
        "api_docs_url": "https://cloud.ru/docs",
        "pricing_url": TARIFF_INDEX_URL,
        "source_url": COMPLIANCE_URL,
        "region_source_url": REGIONS_URL,
        "parsed_at": now_iso(),
    }

    save_json(RAW_DIR / "compliance_raw.json", compliance)
    save_json(RAW_DIR / "regions_raw.json", regions)
    save_json(NORMALIZED_DIR / "providers.json", [provider])
    print(f"Saved provider: {NORMALIZED_DIR / 'providers.json'}")


if __name__ == "__main__":
    main()
