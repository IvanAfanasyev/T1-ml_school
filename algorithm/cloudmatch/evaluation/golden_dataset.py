import json
from pathlib import Path

from algorithm.cloudmatch.schemas.evaluation import GoldenDatasetItem


DEFAULT_GOLDEN_DATASET_FILE = "data/evaluation/golden_dataset.json"


def load_golden_dataset(
    path: str = DEFAULT_GOLDEN_DATASET_FILE,
) -> list[GoldenDatasetItem]:
    """
    Загружает golden dataset из JSON.

    Ожидаемый формат:
    [
      {
        "query_id": "...",
        "query": "...",
        "relevant_service_ids": ["..."],
        "primary_service_id": "...",
        "notes": "..."
      }
    ]
    """

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"Golden dataset not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as file:
        raw_data = json.load(file)

    if not isinstance(raw_data, list):
        raise ValueError("Golden dataset must be a JSON list")

    return [
        GoldenDatasetItem(**item)
        for item in raw_data
    ]