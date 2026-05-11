from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import vk_cloud_config
from common.aggregate import aggregate_providers

_cfg = vk_cloud_config()
NORMALIZED_DIR = _cfg.NORMALIZED_DIR

from app.utils import load_json, save_json


STEPS = [
    ("parse_provider", "parse_vk_provider.py"),
    ("parse_pricelist", "parse_vk_pricelist.py"),
    ("normalize_pricing_items", "normalize_vk_pricing_items.py"),
    ("normalize_services", "normalize_vk_services.py"),
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_step(step_name: str, script: str) -> dict:
    entry = {
        "step": step_name,
        "status": "running",
        "started_at": now(),
        "finished_at": None,
        "error": None,
    }

    try:
        subprocess.run([sys.executable, script], check=True)
        entry["status"] = "success"
    except subprocess.CalledProcessError as exc:
        entry["status"] = "error"
        entry["error"] = str(exc)
        raise
    finally:
        entry["finished_at"] = now()

    return entry


def main() -> None:
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

    log = []
    errors = []

    for step_name, script in STEPS:
        try:
            entry = run_step(step_name, script)
            log.append(entry)
        except Exception as exc:
            log.append({
                "step": step_name,
                "status": "error",
                "started_at": None,
                "finished_at": now(),
                "error": str(exc),
            })
            errors.append({"step": step_name, "error": str(exc)})
            break

    agg_started = now()
    try:
        aggregate_providers()
        log.append({
            "step": "aggregate_providers",
            "status": "success",
            "started_at": agg_started,
            "finished_at": now(),
            "error": None,
        })
    except Exception as exc:
        log.append({
            "step": "aggregate_providers",
            "status": "error",
            "started_at": agg_started,
            "finished_at": now(),
            "error": str(exc),
        })
        errors.append({"step": "aggregate_providers", "error": str(exc)})

    services = []
    items = []
    stats = {}
    llm_errors = []

    try:
        services = load_json(NORMALIZED_DIR / "services.json")
    except Exception:
        pass

    try:
        items = load_json(NORMALIZED_DIR / "service_pricing_items.json")
    except Exception:
        pass

    try:
        stats = load_json(NORMALIZED_DIR / "pricing_items_stats.json")
    except Exception:
        pass

    try:
        llm_errors = load_json(NORMALIZED_DIR / "llm_errors.json")
    except Exception:
        pass

    log.append({
        "step": "summary",
        "status": "success" if not errors else "partial",
        "services_count": len(services),
        "pricing_items_count": len(items),
        "skipped_pricing_rows_count": stats.get("skipped_rows_count"),
        "price_on_request_count": stats.get("price_on_request_count"),
        "llm_errors_count": len(llm_errors),
        "finished_at": now(),
    })

    save_json(NORMALIZED_DIR / "parse_log.json", log)
    save_json(NORMALIZED_DIR / "errors.json", errors)


if __name__ == "__main__":
    main()
