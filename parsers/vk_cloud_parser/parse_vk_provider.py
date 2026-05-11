from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import vk_cloud_config

_cfg = vk_cloud_config()
PROVIDER_ID = _cfg.PROVIDER_ID
PROVIDER_NAME = _cfg.PROVIDER_NAME
BASE_PLATFORM = _cfg.BASE_PLATFORM
COMPLIANCE_URL = _cfg.COMPLIANCE_URL
REGIONS_URL = _cfg.REGIONS_URL
PRICING_URL = _cfg.PRICELIST_URL
RAW_DIR = _cfg.RAW_DIR
NORMALIZED_DIR = _cfg.NORMALIZED_DIR

from app.utils import fetch, clean_text, save_json


# Чтобы не зависеть от наличия DOCS_URL в app/config.py
DOCS_URL = "https://cloud.vk.com/docs"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_compliance() -> dict[str, Any]:
    html = fetch(COMPLIANCE_URL)
    soup = BeautifulSoup(html, "lxml")
    text = clean_text(soup.get_text(" ", strip=True))

    is_152fz = "152" in text and ("персональ" in text.lower() or "фз" in text.lower())
    has_uz1 = "1 уровень защищенности" in text.lower() or "уз-1" in text.lower()
    has_ispdn = "испдн" in text.lower() or "информационная система персональных данных" in text.lower()

    compliance_tags = []
    if is_152fz:
        compliance_tags.append("152-FZ")
    if has_uz1:
        compliance_tags.append("UZ-1")
    if has_ispdn:
        compliance_tags.append("ISPDN")

    certificate_url = None
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if "uz1" in href.lower() or "certificate" in href.lower() or "certificates" in href.lower():
            certificate_url = href
            break

    if not certificate_url and "uz1-2022.pdf" in text:
        certificate_url = "https://app.mcs.st/___files/certificates/uz1-2022.pdf"

    return {
        "source_url": COMPLIANCE_URL,
        "is_152fz_compliant": bool(is_152fz and has_uz1),
        "compliance_tags": compliance_tags,
        "certificate_url": certificate_url,
        "raw_text_preview": text[:3000],
        "parsed_at": _utc_now(),
    }


def _parse_region_table(table) -> list[dict[str, str | None]]:
    rows: list[dict[str, str | None]] = []
    current_region: str | None = None

    for tr in table.find_all("tr"):
        cells = [clean_text(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if not cells:
            continue

        lower = " ".join(cells).lower()
        if "регион" in lower and "зона" in lower and ("дата" in lower or "центр" in lower):
            continue

        if len(cells) >= 3:
            region, az, dc = cells[0], cells[1], cells[2]
            current_region = region
        elif len(cells) == 2 and current_region:
            region, az, dc = current_region, cells[0], cells[1]
        else:
            continue

        az_upper = az.strip().upper()

        # Реальные зоны из страницы VK Cloud: GZ1, MS1, ME1, PA2, QAZ, KTP.
        if az_upper not in {"GZ1", "MS1", "ME1", "PA2", "QAZ", "KTP"}:
            continue

        rows.append({
            "region": region,
            "availability_zone": az_upper,
            "datacenter": dc or None,
        })

    return rows


def parse_regions() -> dict[str, Any]:
    html = fetch(REGIONS_URL)
    soup = BeautifulSoup(html, "lxml")

    region_details: list[dict[str, str | None]] = []

    for table in soup.find_all("table"):
        header_text = clean_text(" ".join(th.get_text(" ", strip=True) for th in table.find_all("th"))).lower()
        table_text = clean_text(table.get_text(" ", strip=True)).lower()

        if (
            ("регион" in header_text or "регион" in table_text)
            and ("зона доступности" in header_text or "зона доступности" in table_text)
            and ("дата-центр" in header_text or "дата-центр" in table_text or "дата центр" in table_text)
        ):
            region_details.extend(_parse_region_table(table))

    seen = set()
    unique_details = []
    for item in region_details:
        key = (item["region"], item["availability_zone"], item["datacenter"])
        if key not in seen:
            seen.add(key)
            unique_details.append(item)

    # Для российского 152-ФЗ в основной список кладём только Москву.
    # Казахстан остаётся в region_details, но не мешает ранжированию.
    russian_details = [
        x for x in unique_details
        if str(x["region"]).strip().lower() in {"москва", "moscow"}
    ]

    main_details = russian_details or unique_details

    regions = []
    for item in main_details:
        reg = item["region"]
        if reg and reg not in regions:
            regions.append(reg)

    availability_zones = []
    for item in main_details:
        az = item["availability_zone"]
        if az and az not in availability_zones:
            availability_zones.append(az)

    return {
        "source_url": REGIONS_URL,
        "regions": regions,
        "availability_zones": availability_zones,
        "region_details": unique_details,
        "parsed_at": _utc_now(),
    }


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

    compliance = parse_compliance()
    regions = parse_regions()

    save_json(RAW_DIR / "compliance_raw.json", compliance)
    save_json(RAW_DIR / "regions_raw.json", regions)

    provider = {
        "provider_id": PROVIDER_ID,
        "name": PROVIDER_NAME,
        "base_platform": BASE_PLATFORM,
        "is_152fz_compliant": compliance["is_152fz_compliant"],
        "regions": regions["regions"],
        "availability_zones": regions["availability_zones"],
        "region_details": regions["region_details"],
        "compliance_tags": compliance["compliance_tags"],
        "compliance_note": (
            "VK Cloud предоставляет услугу «Облако ФЗ-152» для создания виртуальных серверов "
            "и виртуальных дисков в аттестованном периметре ИСПДН. ИСПДН Cloud Servers обеспечивает "
            "1 уровень защищенности персональных данных, что подтверждается аттестатом соответствия."
        ),
        "certificate_url": compliance.get("certificate_url"),
        "api_docs_url": DOCS_URL,
        "pricing_url": PRICING_URL,
        "source_url": COMPLIANCE_URL,
        "region_source_url": REGIONS_URL,
        "parsed_at": _utc_now(),
    }

    save_json(NORMALIZED_DIR / "providers.json", [provider])


if __name__ == "__main__":
    main()
