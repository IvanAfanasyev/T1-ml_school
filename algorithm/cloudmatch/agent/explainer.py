import json
from typing import Any

from algorithm.cloudmatch.llm.client import LLMClient
from algorithm.cloudmatch.llm.prompts.explanation import (
    EXPLANATION_SYSTEM_PROMPT,
    build_explanation_user_prompt,
)


class RankingExplainer:
    """
    Генерирует человекочитаемое объяснение рекомендаций.

    Важно:
    explanation — это дополнительный слой, а не часть ранжирования.
    Если внешний LLM API недоступен, отвечает медленно или вернул невалидный JSON,
    весь pipeline не должен падать. В таком случае строим fallback-объяснение
    из совпавших и неподтверждённых сущностей.
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def explain(
        self,
        payload: dict[str, Any],
    ) -> tuple[str, dict[str, str]]:
        user_prompt = build_explanation_user_prompt(payload)

        try:
            raw_response = self.llm_client.chat(
                system_prompt=EXPLANATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=1800,
            )

            parsed_json = self._parse_json(raw_response)

            return self._build_result_from_llm_json(
                parsed_json=parsed_json,
                payload=payload,
            )

        except Exception as error:
            return self._build_fallback_explanation(
                payload=payload,
                error=error,
            )

    def _parse_json(self, raw_response: str) -> dict[str, Any]:
        cleaned = raw_response.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned.removeprefix("```json").strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```").strip()

        if cleaned.endswith("```"):
            cleaned = cleaned.removesuffix("```").strip()

        data = json.loads(cleaned)

        if not isinstance(data, dict):
            raise ValueError("Explanation response must be a JSON object")

        return data

    def _build_result_from_llm_json(
        self,
        parsed_json: dict[str, Any],
        payload: dict[str, Any],
    ) -> tuple[str, dict[str, str]]:
        summary = parsed_json.get("summary")

        if not summary:
            summary = "Я подобрал провайдеров, которые лучше всего закрывают запрос по имеющимся данным."
        else:
            summary = clean_user_facing_text(str(summary))

        items = parsed_json.get("items", [])

        explanations_by_service_id: dict[str, str] = {}

        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue

                service_id = item.get("service_id")
                explanation = item.get("explanation")

                if service_id and explanation:
                    explanations_by_service_id[str(service_id)] = (
                        clean_user_facing_text(str(explanation))
                    )

        for result in payload.get("top_3", []):
            service_id = result.get("service_id")

            if service_id and service_id not in explanations_by_service_id:
                explanations_by_service_id[service_id] = (
                    self._build_single_fallback_explanation(result)
                )

        return str(summary), explanations_by_service_id

    def _build_fallback_explanation(
        self,
        payload: dict[str, Any],
        error: Exception,
    ) -> tuple[str, dict[str, str]]:
        summary = (
            "Ранжирование выполнено успешно. Подробное объяснение временно "
            "недоступно, поэтому ниже используется объяснение на основе совпавших "
            "и неподтверждённых требований."
        )

        explanations_by_service_id: dict[str, str] = {}

        for result in payload.get("top_3", []):
            service_id = result.get("service_id")

            if not service_id:
                continue

            explanations_by_service_id[service_id] = (
                self._build_single_fallback_explanation(result)
            )

        print()
        print("Warning: LLM explanation failed, fallback explanation was used.")
        print(f"Reason: {type(error).__name__}: {error}")

        return summary, explanations_by_service_id

    def _build_single_fallback_explanation(
        self,
        result: dict[str, Any],
    ) -> str:
        rank = result.get("rank")
        service_name = result.get("service_name")
        provider_name = result.get("provider_name")

        matched = result.get("matched_entities", {})

        matched_tech = matched.get("matched_tech_stack", [])
        missing_tech = matched.get("missing_tech_stack", [])

        matched_use_case = matched.get("matched_use_case", [])
        missing_use_case = matched.get("missing_use_case", [])

        matched_components = matched.get("matched_components", [])
        missing_components = matched.get("missing_components", [])

        matched_requirements = matched.get("matched_requirements", [])
        missing_requirements = matched.get("missing_requirements", [])

        budget_status = matched.get("budget_status")

        parts = [
            f"{rank}. {provider_name} представлен сервисом {service_name}.",
            "Этот вариант полезен как кандидат, потому что в данных есть совпадения с задачей пользователя.",
        ]

        if matched_tech:
            parts.append(f"Совпавшие технологии: {matched_tech}.")

        if missing_tech:
            parts.append(
                f"В данных сервиса явно не найдены технологии: {missing_tech}."
            )

        if matched_use_case:
            parts.append(f"Совпавшие сценарии: {matched_use_case}.")

        if missing_use_case:
            parts.append(
                f"В данных сервиса не подтверждены сценарии: {missing_use_case}."
            )

        if matched_components:
            parts.append(f"Закрытые компоненты: {matched_components}.")

        if missing_components:
            parts.append(
                f"В данных сервиса не подтверждены компоненты: {missing_components}."
            )

        if matched_requirements:
            parts.append(f"Совпавшие дополнительные требования: {matched_requirements}.")

        if missing_requirements:
            parts.append(
                f"Не подтверждены дополнительные требования: {missing_requirements}."
            )

        if budget_status:
            parts.append(format_budget_status_for_user(budget_status))

        return " ".join(parts)


def clean_user_facing_text(text: str) -> str:
    result = text
    forbidden_fragments = [
        "final_score",
        "retrieval_score",
        "entity_match_score",
        "embedding_score",
        "bm25_score",
        "score",
    ]
    for fragment in forbidden_fragments:
        result = result.replace(fragment, "релевантность")
    return result


def format_budget_status_for_user(budget_status: str) -> str:
    messages = {
        "within_budget": "По цене вариант выглядит совместимым с указанным бюджетом.",
        "slightly_over_budget": "Цена близка к бюджету, но может немного его превышать.",
        "over_budget": "По имеющимся тарифам вариант дороже указанного бюджета.",
        "price_unknown": "Точная цена в нормализованных данных не определена.",
        "budget_not_specified": "Бюджет не ограничивал подбор.",
    }
    return messages.get(budget_status, "Бюджет нужно проверить отдельно.")
