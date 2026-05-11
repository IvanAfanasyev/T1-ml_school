from __future__ import annotations

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import t1_cloud_config
from common.aggregate import aggregate_providers

_cfg = t1_cloud_config()
NORMALIZED_DIR = _cfg.NORMALIZED_DIR

import json

from t1_provider_metadata_collector import main as collect_provider_metadata
from t1_tariff_pdf_parser import main as parse_tariff_pdf
from normalize_t1_strict_schema import main as normalize_t1_strict


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def run_step(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    started = now_iso()
    try:
        fn()
        return {
            "step": name,
            "status": "success",
            "started_at": started,
            "finished_at": now_iso(),
            "error": None,
        }
    except Exception as exc:
        return {
            "step": name,
            "status": "error",
            "started_at": started,
            "finished_at": now_iso(),
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


def main() -> None:
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

    steps = [
        ("collect_provider_metadata", collect_provider_metadata),
        ("parse_tariff_pdf", parse_tariff_pdf),
        ("normalize_t1_strict", normalize_t1_strict),
    ]

    logs: list[dict[str, Any]] = []
    for name, fn in steps:
        log = run_step(name, fn)
        logs.append(log)
        if log["status"] != "success":
            break

    logs.append(run_step("aggregate_providers", aggregate_providers))

    services = read_json(NORMALIZED_DIR / "services.json", []) or []
    pricing_items = read_json(NORMALIZED_DIR / "service_pricing_items.json", []) or []
    errors = read_json(NORMALIZED_DIR / "errors.json", []) or []
    llm_errors = read_json(NORMALIZED_DIR / "llm_errors.json", []) or []

    summary = {
        "step": "summary",
        "status": "success" if all(x["status"] == "success" for x in logs) else "partial_error",
        "services_count": len(services),
        "pricing_items_count": len(pricing_items),
        "errors_count": len(errors),
        "llm_errors_count": len(llm_errors),
        "finished_at": now_iso(),
    }
    logs.append(summary)

    write_json(NORMALIZED_DIR / "parse_log.json", logs)
    print("Done")
    print(summary)


if __name__ == "__main__":
    main()
