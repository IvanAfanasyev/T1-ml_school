from typing import Any

from algorithm.cloudmatch.schemas.provider import Provider
from algorithm.cloudmatch.schemas.query import StructuredQuery
from algorithm.cloudmatch.schemas.ranking import RankingResult


def build_difference_reason(
    current: RankingResult,
    previous: RankingResult | None,
) -> dict[str, Any]:
    if previous is None:
        return {
            "why_this_rank": [
                "У этой услуги лучшая итоговая оценка среди выбранных кандидатов.",
                "Она лучше остальных сочетает поисковую близость к запросу и совпадение требований.",
            ],
            "why_lower_than_previous": None,
        }

    reasons = []

    current_scores = current.score_breakdown
    previous_scores = previous.score_breakdown
    current_matched = current.matched_entities

    if current_scores.final_score < previous_scores.final_score:
        reasons.append(
            "Итоговая оценка ниже, чем у предыдущей услуги."
        )

    if current_scores.entity_match_score < previous_scores.entity_match_score:
        reasons.append(
            "Услуга хуже совпала со структурированными требованиями пользователя."
        )

    if current_matched.missing_tech_stack:
        reasons.append(
            f"Не совпали технологии: {current_matched.missing_tech_stack}."
        )

    if current_matched.missing_components:
        reasons.append(
            f"Не закрыты компоненты решения: {current_matched.missing_components}."
        )

    if current_matched.missing_use_case:
        reasons.append(
            f"Не совпали сценарии использования: {current_matched.missing_use_case}."
        )

    if current_matched.missing_requirements:
        reasons.append(
            f"Не выполнены дополнительные требования: {current_matched.missing_requirements}."
        )

    if not reasons:
        reasons.append(
            "Услуга близка к предыдущей, но немного уступила по суммарной оценке."
        )

    return {
        "why_this_rank": [
            "Услуга попала в top-3 после сортировки по итоговой оценке релевантности."
        ],
        "why_lower_than_previous": reasons,
    }


def build_result_payload(
    result: RankingResult,
    provider: Provider | None,
    previous: RankingResult | None,
) -> dict[str, Any]:
    service = result.service
    scores = result.score_breakdown
    matched = result.matched_entities

    return {
        "rank": result.rank,
        "service_id": service.service_id,
        "service_name": service.name,
        "provider_name": provider.name if provider else "Unknown provider",
        "category": service.category,
        "description": service.description,
        "service_fields": {
            "tech_stack_tags": service.tech_stack_tags,
            "use_case_tags": service.use_case_tags,
            "regions": service.regions,
            "pricing_model": service.pricing_model,
            "support_level": service.support_level,
        },
        "price_summary": result.price_summary.model_dump(),
        "score_breakdown": {
            "embedding_score": round(scores.embedding_score, 4),
            "bm25_score": round(scores.bm25_score, 4),
            "retrieval_score": round(scores.retrieval_score, 4),
            "entity_match_score": round(scores.entity_match_score, 4),
            "final_score": round(scores.final_score, 4),
        },
        "matched_entities": {
            "matched_tech_stack": matched.matched_tech_stack,
            "missing_tech_stack": matched.missing_tech_stack,
            "matched_use_case": matched.matched_use_case,
            "missing_use_case": matched.missing_use_case,
            "matched_components": matched.matched_components,
            "missing_components": matched.missing_components,
            "matched_requirements": matched.matched_requirements,
            "missing_requirements": matched.missing_requirements,
            "requirements_score": matched.requirements_score,
            "matched_region": matched.matched_region,
            "budget_status": matched.budget_status,
            "budget_score": matched.budget_score,
        },
        "selected_pricing_items": [
            {
                "item_name": item.item_name,
                "item_type": item.item_type,
                "price_rub": item.price_rub,
                "price_unit": item.price_unit,
                "billing_period": item.billing_period,
                "region": item.region,
                "configuration_tags": item.configuration_tags,
            }
            for item in result.selected_pricing_items
        ],
        "difference_reason": build_difference_reason(
            current=result,
            previous=previous,
        ),
    }


def build_explanation_payload(
    user_query: str,
    structured_query: StructuredQuery,
    results: list[RankingResult],
    providers_by_id: dict[str, Provider],
) -> dict[str, Any]:
    result_payloads = []

    previous_result = None

    for result in results:
        provider = providers_by_id.get(result.service.provider_id)

        result_payloads.append(
            build_result_payload(
                result=result,
                provider=provider,
                previous=previous_result,
            )
        )

        previous_result = result

    return {
        "user_query": user_query,
        "structured_query": structured_query.model_dump(),
        "ranking_policy": {
            "important": "LLM does not choose services. The algorithm already selected top-3.",
            "compliance_rule": "152-FZ is mandatory. Services without confirmed 152-FZ are filtered out before ranking.",
            "retrieval_score_formula": "0.7 * embedding_score + 0.3 * bm25_score",
            "final_score_formula": "0.7 * retrieval_score + 0.3 * entity_match_score",
            "entity_match_includes": [
                "component_match",
                "tech_stack_match",
                "use_case_match",
                "budget_match",
                "requirements_match",
            ],
        },
        "top_3": result_payloads,
    }
