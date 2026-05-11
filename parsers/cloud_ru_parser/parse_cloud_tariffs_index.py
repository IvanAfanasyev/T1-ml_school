from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import cloud_ru_config

_cfg = cloud_ru_config()
RAW_DIR = _cfg.RAW_DIR
TARIFF_INDEX_URL = _cfg.TARIFF_INDEX_URL

from app.utils import absolute_url, clean_text, extract_service_name_from_title, fetch, now_iso, save_json, soup_from_html


def parse_tariffs_index() -> list[dict]:
    html = fetch(TARIFF_INDEX_URL)
    soup = soup_from_html(html)
    services: list[dict] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        title = clean_text(a.get_text(" "))
        if not title.lower().startswith("тарифы"):
            continue
        service_name = extract_service_name_from_title(title)
        if not service_name:
            continue
        url = absolute_url(TARIFF_INDEX_URL, a["href"])
        key = (service_name, url)
        if str(key) in seen:
            continue
        seen.add(str(key))
        services.append({
            "service_name": service_name,
            "title": title,
            "tariff_url": url,
            "source_url": TARIFF_INDEX_URL,
            "parsed_at": now_iso(),
        })

    return services


def main() -> None:
    services = parse_tariffs_index()
    save_json(RAW_DIR / "tariff_index_raw.json", services)
    print(f"Found {len(services)} tariff pages")
    print(f"Saved: {RAW_DIR / 'tariff_index_raw.json'}")


if __name__ == "__main__":
    main()
