from __future__ import annotations

import json
from pathlib import Path

from common.config import DATA_DIR


def aggregate_providers() -> Path:
    """
    Собирает все data/normalized/<provider>/providers.json
    в общий data/normalized/providers.json.

    Дедуп по provider_id — если запись встречается в двух per-provider
    файлах, последняя по алфавиту папок выигрывает.
    """
    normalized_root = DATA_DIR / "normalized"
    output_path = normalized_root / "providers.json"

    by_id: dict[str, dict] = {}

    for provider_dir in sorted(p for p in normalized_root.iterdir() if p.is_dir()):
        per_provider_file = provider_dir / "providers.json"
        if not per_provider_file.exists():
            continue

        try:
            data = json.loads(per_provider_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            continue

        for entry in data:
            if not isinstance(entry, dict):
                continue
            pid = entry.get("provider_id")
            if pid:
                by_id[pid] = entry

    merged = list(by_id.values())
    normalized_root.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


if __name__ == "__main__":
    out = aggregate_providers()
    count = len(json.loads(out.read_text(encoding="utf-8")))
    print(f"Wrote {out} ({count} providers)")
