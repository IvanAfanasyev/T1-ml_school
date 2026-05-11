from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.config import selectel_config as _provider_config

_cfg = _provider_config()
REQUEST_TIMEOUT = _cfg.REQUEST_TIMEOUT
USER_AGENT = _cfg.USER_AGENT


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ").replace("\u202f", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def fetch(url: str) -> str:
    response = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    # Selectel docs sometimes are incorrectly detected by requests as ISO-8859-1.
    # Decode bytes as UTF-8 explicitly to avoid mojibake like "ÐÐ±Ð»Ð°Ñ...".
    return response.content.decode("utf-8", errors="replace")


def soup_from_url(url: str) -> BeautifulSoup:
    return BeautifulSoup(fetch(url), "lxml")


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


_TRANSLIT = str.maketrans({
    "а": "a",  "б": "b",  "в": "v",  "г": "g",  "д": "d",
    "е": "e",  "ё": "yo", "ж": "zh", "з": "z",  "и": "i",
    "й": "y",  "к": "k",  "л": "l",  "м": "m",  "н": "n",
    "о": "o",  "п": "p",  "р": "r",  "с": "s",  "т": "t",
    "у": "u",  "ф": "f",  "х": "kh", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "shch","ъ": "",  "ы": "y",  "ь": "",
    "э": "e",  "ю": "yu", "я": "ya",
})


def slugify(text: str, max_len: int = 90) -> str:
    text = clean_text(text).lower()
    text = text.translate(_TRANSLIT)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len].strip("-") or "item"


def utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def lines_from_element(el) -> list[str]:
    text = el.get_text("\n", strip=True)
    lines = [clean_text(x) for x in text.splitlines()]
    return [x for x in lines if x]
