from algorithm.cloudmatch.core.constants import (
    BM25_WEIGHT,
    EMBEDDING_WEIGHT,
    ENTITY_MATCH_WEIGHT,
    RETRIEVAL_WEIGHT,
)


def calculate_retrieval_score(
    embedding_score: float,
    bm25_score: float,
) -> float:
    """
    Считает поисковую релевантность услуги.

    embedding_score отвечает за смысловую близость.
    bm25_score отвечает за точные совпадения слов.

    Итог:
    retrieval_score = 0.7 * embedding_score + 0.3 * bm25_score
    """

    return (
        EMBEDDING_WEIGHT * embedding_score
        + BM25_WEIGHT * bm25_score
    )


def calculate_final_score(
    retrieval_score: float,
    entity_match_score: float,
) -> float:
    """
    Считает финальную оценку услуги.

    retrieval_score показывает, насколько услуга похожа на запрос.
    entity_match_score показывает, насколько услуга совпала
    со структурированными требованиями пользователя.
    """

    return (
        RETRIEVAL_WEIGHT * retrieval_score
        + ENTITY_MATCH_WEIGHT * entity_match_score
    )