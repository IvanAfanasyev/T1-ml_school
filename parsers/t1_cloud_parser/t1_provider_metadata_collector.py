import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import t1_cloud_config

_cfg = t1_cloud_config()
BASE_URL = _cfg.BASE_URL
RATES_URL = _cfg.RATES_URL
CERTS_URL = _cfg.CERTS_URL
ZONES_URL = _cfg.ZONES_URL
DOCS_URL = _cfg.DOCS_URL

OUT_DIR = _cfg.RAW_DIR
PROVIDER_RAW_PATH = OUT_DIR / "t1_provider_metadata_raw.json"
TARIFF_PDF_PATH = OUT_DIR / "t1_current_tariff.pdf"
TARIFF_INFO_PATH = OUT_DIR / "t1_current_tariff_info.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


class CollectorError(Exception):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    value = str(value).replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def get(url: str, timeout: int = 60) -> requests.Response:
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response


def get_soup(url: str) -> BeautifulSoup:
    response = requests.get(
        url,
        timeout=60,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        },
    )
    response.raise_for_status()

    html = response.content.decode("utf-8", errors="replace")
    return BeautifulSoup(html, "html.parser")

def is_pdf_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.lower().endswith(".pdf")


def score_tariff_link(title: str, url: str) -> int:
    text = f"{title} {url}".lower()
    score = 0

    if "тарифное приложение" in text:
        score += 100
    if "tarif" in text or "тариф" in text:
        score += 50
    if "prilozhenie_1" in text or "приложение" in text:
        score += 20
    if is_pdf_url(url):
        score += 30
    if "архив" in text:
        score -= 100

    # Бонус за дату в ссылке/тексте, чтобы новый документ обычно был выше.
    date_matches = re.findall(r"(20\d{2})", text)
    if date_matches:
        score += max(int(y) for y in date_matches) - 2000

    return score


def find_current_tariff_document() -> dict[str, Any]:
    """
    Ищет актуальную ссылку на тарифное приложение на странице /documents/rates.
    Не хардкодит PDF, чтобы при обновлении сайта забрать свежий документ.
    """
    soup = get_soup(RATES_URL)
    candidates: list[dict[str, Any]] = []

    for a in soup.find_all("a", href=True):
        title = clean_text(a.get_text(" ", strip=True))
        href = urljoin(BASE_URL, a["href"])
        text_for_check = f"{title} {href}".lower()

        if (
            "тарифное приложение" in text_for_check
            or "prilozhenie_1" in text_for_check
            or ("тариф" in text_for_check and is_pdf_url(href))
        ):
            candidates.append(
                {
                    "title": title or Path(urlparse(href).path).name,
                    "url": href,
                    "score": score_tariff_link(title, href),
                }
            )

    if not candidates:
        raise CollectorError("Не нашёл ссылку на тарифное приложение на странице тарифов")

    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Важно: не добавляем candidates внутрь best напрямую.
    # Иначе best уже находится внутри списка candidates, получается circular reference,
    # и json.dumps падает с ValueError: Circular reference detected.
    best = dict(candidates[0])
    found_candidates = [dict(candidate) for candidate in candidates[:10]]

    best["source_page_url"] = RATES_URL
    best["found_candidates"] = found_candidates
    return best


def download_file(url: str, output_path: Path) -> dict[str, Any]:
    response = get(url, timeout=120)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)

    return {
        "url": url,
        "local_path": str(output_path),
        "content_type": response.headers.get("Content-Type", ""),
        "content_length_bytes": len(response.content),
        "downloaded_at": now_utc(),
    }


def score_compliance_link(title: str, url: str) -> int:
    text = f"{title} {url}".lower()
    score = 0

    if "152-фз" in text or "152 фз" in text or "152" in text:
        score += 100
    if "испдн" in text:
        score += 100
    if "аттестат" in text:
        score += 60
    if "соответствия" in text or "соответствие" in text:
        score += 40
    if "сертификат" in text:
        score += 20
    if is_pdf_url(url):
        score += 10

    return score


def find_152fz_evidence() -> dict[str, Any]:
    """
    Ищет на странице сертификатов карточки/ссылки, связанные с 152-ФЗ и ИСПДн.
    Для MVP достаточно публичного title + url, сам PDF глубоко парсить необязательно.
    """
    soup = get_soup(CERTS_URL)
    docs: list[dict[str, Any]] = []

    # На сайте текст карточки может лежать не только внутри <a>, поэтому сначала смотрим ссылки,
    # затем немного расширяем title за счёт родительского блока.
    for a in soup.find_all("a", href=True):
        href = urljoin(BASE_URL, a["href"])
        own_text = clean_text(a.get_text(" ", strip=True))

        parent_text = ""
        parent = a.find_parent()
        if parent:
            parent_text = clean_text(parent.get_text(" ", strip=True))

        title = parent_text or own_text or Path(urlparse(href).path).name
        text_for_check = f"{title} {href}".lower()

        if (
            "152-фз" in text_for_check
            or "152 фз" in text_for_check
            or "испдн" in text_for_check
            or "аттестат соответствия" in text_for_check
        ):
            docs.append(
                {
                    "title": title,
                    "url": href,
                    "is_pdf": is_pdf_url(href),
                    "score": score_compliance_link(title, href),
                }
            )

    # Если ссылка-карточка плохо парсится, проверяем весь текст страницы.
    page_text = clean_text(soup.get_text(" ", strip=True))
    page_text_low = page_text.lower()

    matched_terms = []
    for term in ["152-фз", "152 фз", "испдн", "аттестат соответствия", "персональные данные"]:
        if term in page_text_low:
            matched_terms.append(term)

    # Убираем дубли по URL.
    unique_docs = {}
    for doc in docs:
        old = unique_docs.get(doc["url"])
        if old is None or doc["score"] > old["score"]:
            unique_docs[doc["url"]] = doc

    docs = sorted(unique_docs.values(), key=lambda x: x["score"], reverse=True)

    is_152fz = bool(docs) or "152-фз" in page_text_low or "испдн" in page_text_low

    evidence_excerpt = ""
    if is_152fz:
        # Берём короткий фрагмент вокруг 152-ФЗ/ИСПДн, чтобы сохранить доказательство.
        for keyword in ["152-ФЗ", "ИСПДн", "152 фз"]:
            idx = page_text.lower().find(keyword.lower())
            if idx != -1:
                start = max(0, idx - 180)
                end = min(len(page_text), idx + 260)
                evidence_excerpt = page_text[start:end]
                break

    return {
        "is_152fz_compliant": is_152fz,
        "compliance_tags": ["152-FZ"] if is_152fz else [],
        "compliance_scope": "provider_level" if is_152fz else "unknown",
        "compliance_source_url": CERTS_URL,
        "compliance_matched_terms": matched_terms,
        "compliance_evidence_excerpt": evidence_excerpt,
        "compliance_docs": docs,
    }


def extract_city(address: str) -> Optional[str]:
    address_low = address.lower()
    if "москва" in address_low:
        return "Москва"
    if "санкт-петербург" in address_low or "спб" in address_low:
        return "Санкт-Петербург"
    return None


def parse_zones_table() -> dict[str, Any]:
    """
    Парсит HTML-таблицу зон доступности.
    Для ранжирования потом можно использовать только regions=["Москва"],
    а availability_zones хранить как доказательную детализацию.
    """
    soup = get_soup(ZONES_URL)
    zones: list[dict[str, Any]] = []

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [clean_text(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]

            if len(cells) < 3:
                continue

            first = cells[0].lower()
            if "зона" in first and "доступ" in first:
                continue

            zone_id, datacenter, address = cells[0], cells[1], cells[2]
            if not zone_id or not datacenter or not address:
                continue

            # Сейчас у T1 OpenStack зоны ru-central*, но оставляем мягкую проверку.
            if not (zone_id.startswith("ru-") or "central" in zone_id.lower()):
                continue

            city = extract_city(address)
            zones.append(
                {
                    "zone_id": zone_id,
                    "datacenter": datacenter,
                    "city": city,
                    "country": "RU" if city else None,
                    "address": address,
                    "platform": "OpenStack",
                }
            )

    if not zones:
        raise CollectorError("Не нашёл таблицу зон доступности")

    regions = sorted({z["city"] for z in zones if z.get("city")})
    region_tags = ["RU"] + regions if regions else ["RU"]

    return {
        "regions": regions,
        "region_tags": region_tags,
        "availability_zones": zones,
        "regions_source_url": ZONES_URL,
    }


def build_provider_metadata(download_tariff: bool = True) -> dict[str, Any]:
    tariff_doc = find_current_tariff_document()
    compliance = find_152fz_evidence()
    zones = parse_zones_table()

    tariff_download_info = None
    if download_tariff:
        tariff_download_info = download_file(tariff_doc["url"], TARIFF_PDF_PATH)

    provider = {
        "provider_id": "t1-cloud",
        "name": "Т1 Облако",
        "base_platform": "OpenStack",
        "pricing_url": RATES_URL,
        "api_docs_url": DOCS_URL,
        "current_tariff_document": tariff_doc,
        "current_tariff_download": tariff_download_info,
        "collected_at": now_utc(),
        "source_urls": [
            RATES_URL,
            CERTS_URL,
            ZONES_URL,
            DOCS_URL,
        ],
        **compliance,
        **zones,
    }

    return provider


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    provider = build_provider_metadata(download_tariff=True)

    save_json(provider, PROVIDER_RAW_PATH)
    save_json(provider["current_tariff_document"], TARIFF_INFO_PATH)

    print("Готово")
    print(f"Provider metadata: {PROVIDER_RAW_PATH}")
    print(f"Tariff PDF:        {TARIFF_PDF_PATH}")
    print(f"Tariff info:       {TARIFF_INFO_PATH}")
    print()
    print("Найденный тариф:")
    print(" -", provider["current_tariff_document"].get("title"))
    print(" -", provider["current_tariff_document"].get("url"))
    print()
    print("152-ФЗ:", provider["is_152fz_compliant"])
    print("Регионы:", ", ".join(provider["regions"]) if provider["regions"] else "не найдены")


if __name__ == "__main__":
    main()
