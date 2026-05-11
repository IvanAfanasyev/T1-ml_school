from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch(url: str, timeout: int = 30, retries: int = 3) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"Cannot fetch {url}: {last_error}")


async def fetch_with_playwright(url: str, wait_ms: int = 2500) -> str:
    """Optional fallback for pages rendered by JavaScript."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(locale="ru-RU")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(wait_ms)
        html = await page.content()
        await browser.close()
        return html


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def soup_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return clean_text(soup.get_text(" "))


def slugify(text: str) -> str:
    text = clean_text(text).lower()
    replacements = {
        "&": "and",
        "+": "plus",
        "/": " ",
        "\\": " ",
        ".": " ",
        ",": " ",
        "—": " ",
        "–": " ",
        "_": " ",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"[^a-zа-яё0-9]+", "-", text, flags=re.IGNORECASE)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "unknown"


def normalize_price(value: Any) -> float | None:
    text = clean_text(value).lower()
    if not text or text in {"-", "—", "n/a", "нет", "бесплатно"}:
        if "бесплат" in text:
            return 0.0
        return None

    # remove currency and comments but keep digits separators
    text = text.replace("₽", " ").replace("руб.", " ").replace("руб", " ")
    text = text.replace("тенге", " ").replace("₸", " ")
    text = re.sub(r"[^0-9,\.\-]+", " ", text).strip()
    if not text:
        return None

    # Choose last numeric chunk, often page has multiple labels in one cell.
    nums = re.findall(r"-?\d+(?:[\s,.]\d+)*", text)
    if not nums:
        return None
    raw = nums[-1].replace(" ", "")

    # 1,234.56 -> 1234.56 ; 1 234,56 -> 1234.56 ; 0,001 -> 0.001
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    else:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def normalize_billing_period(value: Any) -> str | None:
    text = clean_text(value).lower()
    if not text:
        return None
    if any(x in text for x in ["мин", "minute", "min"]):
        return "minute"
    if any(x in text for x in ["час", "hour"]):
        return "hour"
    if any(x in text for x in ["сут", "день", "day"]):
        return "day"
    if any(x in text for x in ["месяц", "мес", "30 дней", "month"]):
        return "month"
    if any(x in text for x in ["год", "year"]):
        return "year"
    if any(x in text for x in ["запрос", "request"]):
        return "request"
    return None


def normalize_unit(value: Any) -> str | None:
    text = clean_text(value).lower()
    if not text:
        return None
    text = text.replace("gb", "гб").replace("tb", "тб")
    if "vcpu" in text or "cpu" in text or "ядр" in text:
        return "vcpu"
    if "gpu" in text:
        return "gpu"
    if "гб" in text or "гигабайт" in text:
        return "ГБ"
    if "тб" in text or "терабайт" in text:
        return "ТБ"
    if "мбит" in text or "mbit" in text:
        return "мбит/с"
    if "ip" in text or "адрес" in text:
        return "шт"
    if "запрос" in text or "request" in text:
        return "запрос"
    if "шт" in text or "инстан" in text or "server" in text or "сервер" in text:
        return "шт"
    return clean_text(value)


def make_price_unit(price_currency: str, unit: str | None, period: str | None) -> str:
    unit_part = unit or "unit"
    period_map = {
        "minute": "мин",
        "hour": "час",
        "day": "день",
        "month": "мес",
        "year": "год",
        "request": "запрос",
    }
    period_part = period_map.get(period or "", period or "")
    if period_part:
        return f"{price_currency}/{unit_part}/{period_part}"
    return f"{price_currency}/{unit_part}"


def absolute_url(base: str, href: str | None) -> str | None:
    if not href:
        return None
    return urljoin(base, href)


def looks_like_bad_row(cells: list[str]) -> bool:
    raw = " | ".join(clean_text(c).lower() for c in cells)
    if not raw:
        return True
    bad_patterns = [
        "rows volume",
        "следующая статья",
        "предыдущая статья",
        "примечание",
        "если применимо",
        "показать еще",
        "назад",
        "вперед",
    ]
    if any(p in raw for p in bad_patterns):
        return True
    if len(cells) <= 1 and clean_text(cells[0]).isdigit():
        return True
    # header-like row
    if "стоимость" in raw and "едини" in raw and "период" in raw:
        return True
    return False


def valid_price_period(period: str | None) -> bool:
    return period in {"minute", "hour", "day", "month", "year", "request"}
