"""
Standalone script: собирает все per-provider providers.json
в общий data/normalized/providers.json.

Использование:
    python aggregate_providers.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.aggregate import aggregate_providers


def main() -> None:
    out = aggregate_providers()
    count = len(json.loads(out.read_text(encoding="utf-8")))
    print(f"Wrote {out} ({count} providers)")


if __name__ == "__main__":
    main()
