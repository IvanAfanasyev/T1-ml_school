from algorithm.cloudmatch.schemas.evaluation import QueryEvaluationResult


def precision_at_k(
    retrieved_ids: list[str],
    relevant_ids: list[str],
    k: int,
) -> float:
    """
    Считает Precision@k.

    Precision@k = количество релевантных документов в top-k / k
    """

    if k <= 0:
        raise ValueError("k must be positive")

    top_k_ids = retrieved_ids[:k]
    relevant_set = set(relevant_ids)

    if not top_k_ids:
        return 0.0

    hits = sum(
        1
        for service_id in top_k_ids
        if service_id in relevant_set
    )

    return hits / k


def reciprocal_rank(
    retrieved_ids: list[str],
    relevant_ids: list[str],
) -> tuple[float, int | None]:
    """
    Считает Reciprocal Rank для одного запроса.

    Возвращает:
    - reciprocal_rank
    - rank первого релевантного сервиса
    """

    relevant_set = set(relevant_ids)

    for index, service_id in enumerate(retrieved_ids, start=1):
        if service_id in relevant_set:
            return 1.0 / index, index

    return 0.0, None


def find_rank(
    retrieved_ids: list[str],
    target_id: str | None,
) -> int | None:
    """
    Возвращает позицию конкретного service_id в выдаче.

    Если target_id не найден, возвращает None.
    """

    if target_id is None:
        return None

    for index, service_id in enumerate(retrieved_ids, start=1):
        if service_id == target_id:
            return index

    return None


def mean_precision_at_3(
    results: list[QueryEvaluationResult],
) -> float:
    if not results:
        return 0.0

    return sum(item.precision_at_3 for item in results) / len(results)


def mean_reciprocal_rank(
    results: list[QueryEvaluationResult],
) -> float:
    if not results:
        return 0.0

    return sum(item.reciprocal_rank for item in results) / len(results)