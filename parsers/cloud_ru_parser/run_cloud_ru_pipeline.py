from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import cloud_ru_config
from common.aggregate import aggregate_providers

_cfg = cloud_ru_config()
NORMALIZED_DIR = _cfg.NORMALIZED_DIR
RAW_DIR = _cfg.RAW_DIR

from parse_cloud_provider import main as parse_provider
from parse_cloud_tariffs_index import main as parse_index
from parse_cloud_tariff_page import main as parse_pages
from normalize_cloud_pricing_items import main as normalize_pricing
from normalize_cloud_services import main as normalize_services
from app.utils import load_json, now_iso, save_json


def main() -> None:
    logs = []
    steps = [
        ("parse_provider", parse_provider),
        ("parse_tariffs_index", parse_index),
        ("parse_tariff_pages", parse_pages),
        ("normalize_pricing_items", normalize_pricing),
        ("normalize_services", normalize_services),
    ]
    for name, func in steps:
        started = now_iso()
        try:
            func()
            logs.append({"step": name, "status": "success", "started_at": started, "finished_at": now_iso(), "error": None})
        except Exception as exc:
            logs.append({"step": name, "status": "error", "started_at": started, "finished_at": now_iso(), "error": str(exc)})
            raise

    started = now_iso()
    try:
        aggregate_providers()
        logs.append({"step": "aggregate_providers", "status": "success", "started_at": started, "finished_at": now_iso(), "error": None})
    except Exception as exc:
        logs.append({"step": "aggregate_providers", "status": "error", "started_at": started, "finished_at": now_iso(), "error": str(exc)})

    services = load_json(NORMALIZED_DIR / "services.json", [])
    pricing = load_json(NORMALIZED_DIR / "service_pricing_items.json", [])
    logs.append({
        "step": "summary",
        "status": "success",
        "services_count": len(services),
        "pricing_items_count": len(pricing),
        "finished_at": now_iso(),
    })
    save_json(NORMALIZED_DIR / "parse_log.json", logs)
    print(f"Pipeline done. Output: {NORMALIZED_DIR}")


if __name__ == "__main__":
    main()
