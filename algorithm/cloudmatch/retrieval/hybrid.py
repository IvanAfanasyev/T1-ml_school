from typing import Any

from algorithm.cloudmatch.core.constants import RETRIEVAL_SERVICE_CANDIDATES_LIMIT
from algorithm.cloudmatch.ranking.scoring import calculate_retrieval_score
from algorithm.cloudmatch.retrieval.bm25 import BM25Scorer
from algorithm.cloudmatch.retrieval.embeddings import EmbeddingScorer
from algorithm.cloudmatch.schemas.query import QueryRequirement, StructuredQuery
from algorithm.cloudmatch.schemas.ranking import RankingCandidate, ScoreBreakdown
from algorithm.cloudmatch.schemas.service import Service


def stringify_value(value: Any) -> str:
    """
    Превращает любое значение requirement в строку для retrieval query.

    Например:
    true -> "true"
    ["gpu", "a100"] -> "gpu a100"
    {"min": 99.9} -> "min 99.9"
    """

    if value is None:
        return ""

    if isinstance(value, list):
        return " ".join(stringify_value(item) for item in value)

    if isinstance(value, dict):
        parts = []

        for key, item in value.items():
            parts.append(str(key))
            parts.append(stringify_value(item))

        return " ".join(parts)

    return str(value)


def build_requirements_text(requirements: list[QueryRequirement]) -> str:
    """
    Добавляет requirements в retrieval query.

    Это нужно, чтобы даже пока не обрабатываемые критерии
    участвовали в BM25/embedding search.
    """

    parts = []

    for requirement in requirements:
        parts.append(requirement.name)
        parts.append(stringify_value(requirement.value))

        if requirement.source_text:
            parts.append(requirement.source_text)

        if requirement.reason:
            parts.append(requirement.reason)

    return " ".join(part for part in parts if part)


def build_retrieval_query_text(query: StructuredQuery) -> str:
    """
    Собирает текст для RAG/retrieval.

    Принцип:
    - используем raw_query;
    - используем структурированные поля;
    - не теряем новые технологии и новые требования;
    - requirements тоже идут в retrieval query,
      даже если для них пока нет отдельного matcher.
    """

    component_parts = []
    db_engine_parts = []
    subtype_parts = []

    for component in query.required_components:
        component_parts.append(component.component)

        if component.db_engine:
            db_engine_parts.append(component.db_engine)

        if component.subtype:
            subtype_parts.append(component.subtype)

        if component.reason:
            component_parts.append(component.reason)

    requirements_text = build_requirements_text(query.requirements)
    extracted_entities_text = build_requirements_text(query.extracted_entities)
    additional_constraints_text = build_requirements_text(query.constraints.additional)

    parts = [
        query.raw_query,
        query.task_category or "",
        query.intent or "",
        " ".join(query.tech_stack),
        " ".join(query.use_case),
        " ".join(component_parts),
        " ".join(db_engine_parts),
        " ".join(subtype_parts),
        query.constraints.region or "",
        query.constraints.effective_region or "",
        requirements_text,
        extracted_entities_text,
        additional_constraints_text,
    ]

    return " ".join(part for part in parts if part).lower()


class HybridRetriever:
    """
    Первичный поиск услуг-кандидатов.

    Внутри:
    - BM25 для точных совпадений;
    - embeddings для смысловой близости;
    - retrieval_score для объединения двух сигналов.
    """

    def __init__(
        self,
        bm25_scorer: BM25Scorer | None = None,
        embedding_scorer: EmbeddingScorer | None = None,
    ) -> None:
        self.bm25_scorer = bm25_scorer or BM25Scorer()
        self.embedding_scorer = embedding_scorer or EmbeddingScorer()

    def retrieve(
        self,
        query: StructuredQuery,
        services: list[Service],
        limit: int = RETRIEVAL_SERVICE_CANDIDATES_LIMIT,
    ) -> list[RankingCandidate]:
        """
        Возвращает top-N услуг по retrieval_score.

        На этом этапе считаем:
        - embedding_score;
        - bm25_score;
        - retrieval_score.

        Здесь ещё не считаем:
        - entity_match_score;
        - budget_score;
        - final_score.
        """

        if not services:
            return []

        query_text = build_retrieval_query_text(query)

        bm25_scores = self.bm25_scorer.score(
            query_text=query_text,
            services=services,
        )

        embedding_scores = self.embedding_scorer.score(
            query_text=query_text,
            services=services,
        )

        candidates = []

        for service in services:
            bm25_score = bm25_scores.get(service.service_id, 0.0)
            embedding_score = embedding_scores.get(service.service_id, 0.0)

            retrieval_score = calculate_retrieval_score(
                embedding_score=embedding_score,
                bm25_score=bm25_score,
            )

            candidate = RankingCandidate(
                service=service,
                score_breakdown=ScoreBreakdown(
                    embedding_score=embedding_score,
                    bm25_score=bm25_score,
                    retrieval_score=retrieval_score,
                    entity_match_score=0.0,
                    final_score=0.0,
                ),
            )

            candidates.append(candidate)

        candidates.sort(
            key=lambda candidate: candidate.score_breakdown.retrieval_score,
            reverse=True,
        )

        return candidates[:limit]
