from algorithm.cloudmatch.core.constants import TOP_K_RECOMMENDATIONS
from algorithm.cloudmatch.schemas.ranking import RankingCandidate, RankingResult


def select_top_k(
    candidates: list[RankingCandidate],
    top_k: int = TOP_K_RECOMMENDATIONS,
) -> list[RankingResult]:
    """
    Сортирует кандидатов по final_score и возвращает top-k.
    """

    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: candidate.score_breakdown.final_score,
        reverse=True,
    )

    results = []

    for index, candidate in enumerate(sorted_candidates[:top_k], start=1):
        results.append(
            RankingResult(
                rank=index,
                service=candidate.service,
                selected_pricing_items=candidate.selected_pricing_items,
                price_summary=candidate.price_summary,
                score_breakdown=candidate.score_breakdown,
                matched_entities=candidate.matched_entities,
                explanation=None,
            )
        )

    return results