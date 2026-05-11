from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.config import cloud_ru_config as _provider_config

_cfg = _provider_config()
REQUEST_TIMEOUT = _cfg.REQUEST_TIMEOUT
USER_AGENT = _cfg.USER_AGENT


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def fetch(url: str) -> str:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def slugify(value: str) -> str:
    value = value.lower().strip()
    replacements = {
        "&": "and",
        "+": "plus",
        "№": "",
        "«": "",
        "»": "",
        '"': "",
        "'": "",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"[^a-zа-я0-9]+", "-", value, flags=re.IGNORECASE)
    value = value.strip("-")
    return value or hashlib.md5(value.encode("utf-8")).hexdigest()[:8]


def normalize_price(value: Any) -> float | None:
    text = clean_text(value)
    if not text or text in {"-", "—", "nan", "None"}:
        return None
    text = text.replace(" ", "").replace(",", ".")
    text = re.sub(r"[^0-9.]", "", text)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_billing_period(value: str) -> str | None:
    text = clean_text(value).lower()
    mapping = {
        "час": "hour",
        "месяц": "month",
        "сутки": "day",
        "день": "day",
        "год": "year",
        "разово": "one_time",
        "запрос": "request",
    }
    for ru, norm in mapping.items():
        if ru in text:
            return norm
    return text or None


def normalize_unit(value: str, period: str | None = None) -> str | None:
    text = clean_text(value).lower()
    if not text:
        return None
    unit_map = {
        "гб": "ГБ",
        "gb": "ГБ",
        "шт": "шт",
        "тыс. шт": "1000 шт",
        "тыс шт": "1000 шт",
        "vсpu": "vCPU",
        "vcpu": "vCPU",
    }
    unit = text
    for raw, norm in unit_map.items():
        if raw in text:
            unit = norm
            break
    period_ru = {
        "hour": "час",
        "month": "мес",
        "day": "день",
        "year": "год",
        "one_time": "разово",
        "request": "запрос",
    }.get(period or "", period or "")
    return f"руб/{unit}/{period_ru}" if period_ru else f"руб/{unit}"


def extract_service_name_from_title(text: str) -> str:
    text = clean_text(text)
    m = re.search(r"Тарифы\s+[«\"](.+?)[»\"]", text)
    if m:
        return clean_text(m.group(1))
    text = re.sub(r"^Тарифы\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\.\s*Приложение.*$", "", text, flags=re.IGNORECASE)
    return clean_text(text)


def absolute_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)
