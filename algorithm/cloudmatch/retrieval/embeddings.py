import os
import logging
import warnings

# Отключаем лишний вывод Hugging Face / Transformers
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"

warnings.filterwarnings("ignore")

logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

from algorithm.cloudmatch.core.hf_quiet import quiet_huggingface_output

quiet_huggingface_output()

try:
    from huggingface_hub.utils import disable_progress_bars

    disable_progress_bars()
except Exception:
    pass

try:
    from transformers.utils import logging as transformers_logging

    transformers_logging.set_verbosity_error()
except Exception:
    pass

from sentence_transformers import SentenceTransformer


import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from algorithm.cloudmatch.core.constants import (
    EMBEDDING_MODEL_NAME,
    SERVICE_EMBEDDINGS_FILE,
    SERVICE_IDS_FILE,
)
from algorithm.cloudmatch.schemas.service import Service


class EmbeddingScorer:
    """
    Настоящий embedding scorer.

    Он сравнивает query_text с заранее посчитанными embeddings услуг.

    Важно:
    - услуги ранжируются по service_id;
    - embeddings строятся заранее через algorithm/scripts/build_indexes.py;
    - если services.json обновился, индекс нужно перестроить.
    """

    def __init__(self) -> None:
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        self.service_ids = self._load_service_ids()
        self.service_embeddings = self._load_service_embeddings()

        if len(self.service_ids) != len(self.service_embeddings):
            raise ValueError(
                "Количество service_ids не совпадает с количеством embeddings. "
                "Перестрой индекс через: python -m algorithm.scripts.build_indexes"
            )

        self.service_id_to_index = {
            service_id: index
            for index, service_id in enumerate(self.service_ids)
        }

    def score(
        self,
        query_text: str,
        services: list[Service],
    ) -> dict[str, float]:
        """
        Возвращает:
        {
            service_id: embedding_score
        }

        Считаем score только для тех services,
        которые пришли после hard filters.
        """

        if not services:
            return {}

        query_embedding = self.model.encode(
            [query_text],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0]

        scores = {}

        for service in services:
            index = self.service_id_to_index.get(service.service_id)

            if index is None:
                # Такое возможно, если services.json обновился,
                # а индекс embeddings не перестроили.
                scores[service.service_id] = 0.0
                continue

            service_embedding = self.service_embeddings[index]

            similarity = float(np.dot(query_embedding, service_embedding))

            # cosine similarity может быть от -1 до 1.
            # Для scoring удобнее привести к диапазону 0..1.
            normalized_similarity = (similarity + 1.0) / 2.0

            scores[service.service_id] = normalized_similarity

        return scores

    def _load_service_ids(self) -> list[str]:
        path = Path(SERVICE_IDS_FILE)

        if not path.exists():
            raise FileNotFoundError(
                f"Не найден файл service_ids: {path}. "
                "Сначала запусти: python -m algorithm.scripts.build_indexes"
            )

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError(f"Файл {path} должен содержать список service_id")

        return [str(item) for item in data]

    def _load_service_embeddings(self) -> np.ndarray:
        path = Path(SERVICE_EMBEDDINGS_FILE)

        if not path.exists():
            raise FileNotFoundError(
                f"Не найден файл embeddings: {path}. "
                "Сначала запусти: python -m algorithm.scripts.build_indexes"
            )

        return np.load(path)