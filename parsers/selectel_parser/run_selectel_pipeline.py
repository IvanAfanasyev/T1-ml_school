from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Callable, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import selectel_config
from common.aggregate import aggregate_providers

_cfg = selectel_config()
NORMALIZED_DIR = _cfg.NORMALIZED_DIR

from app.utils import save_json, load_json, utc_now_iso


def run_step(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    started = utc_now_iso()
    try:
        result = fn()
        return {
            "step": name,
            "status": "success",
            "started_at": started,
            "finished_at": utc_now_iso(),
            "error": None,
        }
    except Exception as e:
        return {
            "step": name,
            "status": "error",
            "started_at": started,
            "finished_at": utc_now_iso(),
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


def main() -> None:
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    logs = []

    from parse_selectel_provider import main as parse_provider
    from parse_selectel_availability import main as parse_availability
    from parse_selectel_prices import main as parse_prices
    from normalize_selectel_pricing_items import normalize as normalize_pricing
    from normalize_selectel_services import normalize_services

    steps = [
        ("parse_provider", parse_provider),
        ("parse_availability", parse_availability),
        ("parse_prices", parse_prices),
        ("normalize_pricing_items", normalize_pricing),
        ("normalize_services", normalize_services),
    ]

    for name, fn in steps:
        log = run_step(name, fn)
        logs.append(log)
        if log["status"] != "success":
            break

    logs.append(run_step("aggregate_providers", aggregate_providers))

    services = load_json(NORMALIZED_DIR / "services.json", []) or []
    pricing_items = load_json(NORMALIZED_DIR / "service_pricing_items.json", []) or []
    availability = load_json(NORMALIZED_DIR / "service_availability.json", []) or []
    stats = load_json(NORMALIZED_DIR / "pricing_items_stats.json", {}) or {}
    llm_errors = load_json(NORMALIZED_DIR / "llm_errors.json", []) or []

    summary = {
        "step": "summary",
        "status": "success" if all(x["status"] == "success" for x in logs) else "partial_error",
        "services_count": len(services),
        "pricing_items_count": len(pricing_items),
        "availability_items_count": len(availability),
        "skipped_pricing_rows_count": stats.get("skipped_rows_count", 0),
        "price_on_request_count": stats.get("price_on_request_count", 0),
        "llm_errors_count": len(llm_errors),
        "finished_at": utc_now_iso(),
    }
    logs.append(summary)

    save_json(NORMALIZED_DIR / "parse_log.json", logs)
    save_json(NORMALIZED_DIR / "errors.json", [x for x in logs if x.get("status") == "error"])

    print("Done")
    print(summary)


if __name__ == "__main__":
    main()
