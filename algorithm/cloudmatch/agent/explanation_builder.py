from typing import Any

from algorithm.cloudmatch.schemas.provider import Provider
from algorithm.cloudmatch.schemas.query import StructuredQuery
from algorithm.cloudmatch.schemas.ranking import RankingResult


def build_difference_reason(
    current: RankingResult,
    previous: RankingResult | None,
) -> dict[str, Any]:
    matched = current.matched_entities

    if previous is None:
        return {
            "why_this_rank": [
                "Провайдер хорошо закрывает ключевые требования запроса.",
                "В данных есть прямые совпадения по задаче пользователя.",
            ],
            "why_lower_than_previous": None,
        }

    reasons = []
    previous_matched = previous.matched_entities

    if matched.missing_tech_stack:
        reasons.append(
            f"В данных не подтверждены технологии: {matched.missing_tech_stack}."
        )

    if matched.missing_components:
        reasons.append(
            f"В данных не подтверждены компоненты решения: {matched.missing_components}."
        )

    if matched.missing_use_case:
        reasons.append(
            f"В данных не подтверждены сценарии использования: {matched.missing_use_case}."
        )

    if matched.missing_requirements:
        reasons.append(
            f"В данных не подтверждены дополнительные требования: {matched.missing_requirements}."
        )

    if (
        matched.budget_status in {"over_budget", "slightly_over_budget"}
        and previous_matched.budget_status == "within_budget"
    ):
        reasons.append("Цена выглядит выше указанного бюджета.")

    if not reasons:
        reasons.append(
            "Провайдер тоже подходит под запрос, но требует такой же ручной проверки цены, региона или отдельных свойств сервиса."
        )

    return {
        "why_this_rank": [
            "Провайдер попал в список рекомендаций благодаря совпадениям с требованиями пользователя."
        ],
        "why_lower_than_previous": reasons,
    }


def build_result_payload(
    result: RankingResult,
    provider: Provider | None,
    previous: RankingResult | None,
) -> dict[str, Any]:
    service = result.service
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
        "matched_entities": {
            "matched_tech_stack": matched.matched_tech_stack,
            "missing_tech_stack": matched.missing_tech_stack,
            "matched_use_case": matched.matched_use_case,
            "missing_use_case": matched.missing_use_case,
            "matched_components": matched.matched_components,
            "missing_components": matched.missing_components,
            "matched_requirements": matched.matched_requirements,
            "missing_requirements": matched.missing_requirements,
            "matched_region": matched.matched_region,
            "budget_status": matched.budget_status,
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
            "important": "LLM does not choose providers or services. The algorithm already selected the recommendations.",
            "ranking_mode": "simple requests return top providers; each provider is represented by its strongest matching service.",
            "compliance_rule": "152-FZ is mandatory. Services without confirmed 152-FZ are filtered out before ranking.",
            "forbidden_user_facing_wording": [
                "Do not mention score, final_score, retrieval_score, entity_match_score, embedding_score, bm25_score.",
                "Do not explain that an item is second or third because its score is lower.",
                "Explain only concrete matched and missing requirements, price availability, region and role fit.",
            ],
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
