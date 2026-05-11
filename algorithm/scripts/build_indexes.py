import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from algorithm.cloudmatch.core.constants import (
    EMBEDDING_MODEL_NAME,
    SERVICE_EMBEDDINGS_FILE,
    SERVICE_IDS_FILE,
)
from algorithm.cloudmatch.data.repositories import DataRepository
from algorithm.cloudmatch.data.service_text import build_service_text


def main() -> None:
    print("Загружаем services.json...")

    repository = DataRepository()
    services = repository.get_all_services()

    if not services:
        print("В services.json нет услуг. Индекс не построен.")
        return

    print(f"Услуг найдено: {len(services)}")

    print("Собираем service_text для каждой услуги...")

    service_ids = [service.service_id for service in services]
    service_texts = [build_service_text(service) for service in services]

    print(f"Загружаем embedding-модель: {EMBEDDING_MODEL_NAME}")

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    print("Считаем embeddings услуг...")

    embeddings = model.encode(
        service_texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    embeddings_path = Path(SERVICE_EMBEDDINGS_FILE)
    service_ids_path = Path(SERVICE_IDS_FILE)

    embeddings_path.parent.mkdir(parents=True, exist_ok=True)
    service_ids_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Сохраняем embeddings: {embeddings_path}")
    np.save(embeddings_path, embeddings)

    print(f"Сохраняем service_ids: {service_ids_path}")
    with service_ids_path.open("w", encoding="utf-8") as file:
        json.dump(service_ids, file, ensure_ascii=False, indent=2)

    print("Embedding index успешно построен.")


if __name__ == "__main__":
    main()