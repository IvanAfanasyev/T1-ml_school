import json
from typing import Any

from algorithm.cloudmatch.llm.client import LLMClient
from algorithm.cloudmatch.llm.prompts.judge import (
    JUDGE_SYSTEM_PROMPT,
    build_judge_user_prompt,
)
from algorithm.cloudmatch.schemas.evaluation import GoldenDatasetItem
from algorithm.cloudmatch.schemas.ranking import SearchResponse


class LLMJudge:
    """
    LLM-as-a-judge для оценки качества ответа.

    Judge не выбирает сервисы заново.
    Judge оценивает уже готовый top-3.

    Если LLM API не отвечает, возвращается fallback,
    но в результате явно будет judge_source="fallback".
    Настоящая LLM-оценка имеет judge_source="llm".
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        max_attempts: int = 3,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.max_attempts = max_attempts

    def judge(
        self,
        golden_item: GoldenDatasetItem,
        response: SearchResponse,
        precision_at_3: float,
        reciprocal_rank: float,
    ) -> dict[str, Any]:
        payload = self._build_tiny_payload(
            golden_item=golden_item,
            response=response,
            precision_at_3=precision_at_3,
            reciprocal_rank=reciprocal_rank,
        )

        last_error: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                raw_response = self.llm_client.chat(
                    system_prompt=JUDGE_SYSTEM_PROMPT,
                    user_prompt=build_judge_user_prompt(payload),
                    max_tokens=3000,
                )

                if not raw_response or not raw_response.strip():
                    raise ValueError("LLM returned empty response")

                parsed = self._parse_json(raw_response)
                normalized = self._normalize_judge_response(parsed)

                normalized["judge_source"] = "llm"
                normalized["judge_attempts"] = attempt

                return normalized

            except Exception as error:
                last_error = error
                payload = self._build_even_smaller_payload(payload)

        return self._fallback_response(
            golden_item=golden_item,
            response=response,
            precision_at_3=precision_at_3,
            reciprocal_rank=reciprocal_rank,
            error=last_error,
        )

    def _build_tiny_payload(
        self,
        golden_item: GoldenDatasetItem,
        response: SearchResponse,
        precision_at_3: float,
        reciprocal_rank: float,
    ) -> dict[str, Any]:
        top_3 = []

        for result in response.results:
            service = result.service
            scores = result.score_breakdown
            matched = result.matched_entities

            top_3.append(
                {
                    "rank": result.rank,
                    "service_id": service.service_id,
                    "name": service.name,
                    "provider_id": service.provider_id,
                    "category": service.category,
                    "final_score": round(scores.final_score, 4),
                    "retrieval_score": round(scores.retrieval_score, 4),
                    "entity_match_score": round(scores.entity_match_score, 4),
                    "matched": {
                        "tech": matched.matched_tech_stack,
                        "use_case": matched.matched_use_case,
                        "components": matched.matched_components,
                        "requirements": matched.matched_requirements,
                    },
                    "missing": {
                        "tech": matched.missing_tech_stack,
                        "use_case": matched.missing_use_case,
                        "components": matched.missing_components,
                        "requirements": matched.missing_requirements,
                    },
                    "explanation": self._clip(result.explanation, 300),
                }
            )

        return {
            "query": golden_item.query,
            "expected_relevant_ids": golden_item.relevant_service_ids,
            "primary_expected_id": golden_item.primary_service_id,
            "retrieved_ids": [
                result.service.service_id
                for result in response.results
            ],
            "precision_at_3": round(precision_at_3, 4),
            "reciprocal_rank": round(reciprocal_rank, 4),
            "structured_query": {
                "tech_stack": response.structured_query.get("tech_stack"),
                "use_case": response.structured_query.get("use_case"),
                "requirements": response.structured_query.get("requirements"),
                "constraints": response.structured_query.get("constraints"),
            },
            "top_3": top_3,
        }

    def _build_even_smaller_payload(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Вторая/третья попытка: максимально короткий payload.
        """

        smaller_top = []

        for item in payload.get("top_3", []):
            smaller_top.append(
                {
                    "rank": item.get("rank"),
                    "service_id": item.get("service_id"),
                    "name": item.get("name"),
                    "final_score": item.get("final_score"),
                    "matched": item.get("matched"),
                    "missing": item.get("missing"),
                }
            )

        return {
            "query": payload.get("query"),
            "expected_relevant_ids": payload.get("expected_relevant_ids"),
            "retrieved_ids": payload.get("retrieved_ids"),
            "precision_at_3": payload.get("precision_at_3"),
            "reciprocal_rank": payload.get("reciprocal_rank"),
            "top_3": smaller_top,
        }

    def _clip(
        self,
        value: Any,
        max_chars: int,
    ) -> str:
        if value is None:
            return ""

        text = str(value)

        if len(text) <= max_chars:
            return text

        return text[:max_chars] + "..."

    def _parse_json(self, raw_response: str) -> dict[str, Any]:
        cleaned = raw_response.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned.removeprefix("```json").strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```").strip()

        if cleaned.endswith("```"):
            cleaned = cleaned.removesuffix("```").strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start:end + 1]

        data = json.loads(cleaned)

        if not isinstance(data, dict):
            raise ValueError("Judge response must be JSON object")

        return data

    def _normalize_score(self, value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0

        if score < 0:
            return 0.0

        if score > 1:
            return 1.0

        return score

    def _normalize_string_list(self, value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            return [value]

        if not isinstance(value, list):
            return []

        return [
            str(item)
            for item in value
            if item is not None
        ]

    def _normalize_judge_response(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        verdict = str(data.get("verdict", "warn")).strip().lower()

        if verdict not in {"pass", "warn", "fail"}:
            verdict = "warn"

        return {
            "relevance_score": self._normalize_score(
                data.get("relevance_score")
            ),
            "ranking_order_score": self._normalize_score(
                data.get("ranking_order_score")
            ),
            "explanation_faithfulness_score": self._normalize_score(
                data.get("explanation_faithfulness_score")
            ),
            "missing_requirements_handling_score": self._normalize_score(
                data.get("missing_requirements_handling_score")
            ),
            "usefulness_score": self._normalize_score(
                data.get("usefulness_score")
            ),
            "overall_score": self._normalize_score(
                data.get("overall_score")
            ),
            "verdict": verdict,
            "strengths": self._normalize_string_list(
                data.get("strengths")
            ),
            "issues": self._normalize_string_list(
                data.get("issues")
            ),
            "recommendations": self._normalize_string_list(
                data.get("recommendations")
            ),
        }

    def _fallback_response(
        self,
        golden_item: GoldenDatasetItem,
        response: SearchResponse,
        precision_at_3: float,
        reciprocal_rank: float,
        error: Exception | None,
    ) -> dict[str, Any]:
        """
        Аварийная оценка.

        Это НЕ LLM-as-a-judge.
        Она нужна только для того, чтобы evaluation не падал.
        """

        relevance_score = min(1.0, precision_at_3)
        ranking_order_score = reciprocal_rank
        faithfulness_score = self._rule_based_faithfulness(response)
        missing_score = self._rule_based_missing_handling(response)

        usefulness_score = max(
            0.0,
            min(
                1.0,
                0.5 * relevance_score + 0.5 * ranking_order_score,
            ),
        )

        overall_score = (
            0.30 * relevance_score
            + 0.20 * ranking_order_score
            + 0.20 * faithfulness_score
            + 0.15 * missing_score
            + 0.15 * usefulness_score
        )

        if overall_score >= 0.8:
            verdict = "pass"
        elif overall_score >= 0.55:
            verdict = "warn"
        else:
            verdict = "fail"

        issue = "LLM judge failed"

        if error is not None:
            issue = f"LLM judge failed: {type(error).__name__}: {error}"

        return {
            "relevance_score": round(relevance_score, 4),
            "ranking_order_score": round(ranking_order_score, 4),
            "explanation_faithfulness_score": round(faithfulness_score, 4),
            "missing_requirements_handling_score": round(missing_score, 4),
            "usefulness_score": round(usefulness_score, 4),
            "overall_score": round(overall_score, 4),
            "verdict": verdict,
            "strengths": [
                "Fallback judge used automatic metrics and matched/missing entities."
            ],
            "issues": [
                issue,
                "This is not a real LLM-as-a-judge result."
            ],
            "recommendations": [
                "Retry with smaller payload or use a lighter judge model."
            ],
            "judge_source": "fallback",
            "judge_attempts": self.max_attempts,
        }

    def _rule_based_faithfulness(
        self,
        response: SearchResponse,
    ) -> float:
        if not response.results:
            return 0.0

        total = 0
        ok = 0

        for result in response.results:
            explanation = (result.explanation or "").lower()
            matched = result.matched_entities

            missing_values = []
            missing_values.extend(matched.missing_tech_stack)
            missing_values.extend(matched.missing_components)
            missing_values.extend(matched.missing_requirements)

            for value in missing_values:
                total += 1
                value_text = str(value).lower()

                bad_phrases = [
                    f"поддерживает {value_text}",
                    f"предоставляет {value_text}",
                    f"закрывает {value_text}",
                    f"есть {value_text}",
                ]

                if not any(phrase in explanation for phrase in bad_phrases):
                    ok += 1

        if total == 0:
            return 1.0

        return ok / total

    def _rule_based_missing_handling(
        self,
        response: SearchResponse,
    ) -> float:
        if not response.results:
            return 0.0

        total_with_missing = 0
        explained_missing = 0

        for result in response.results:
            explanation = (result.explanation or "").lower()
            matched = result.matched_entities

            missing_values = []
            missing_values.extend(matched.missing_tech_stack)
            missing_values.extend(matched.missing_components)
            missing_values.extend(matched.missing_requirements)

            if not missing_values:
                continue

            total_with_missing += 1

            if (
                "не подтвержден" in explanation
                or "не найден" in explanation
                or "не указ" in explanation
                or "missing" in explanation
            ):
                explained_missing += 1

        if total_with_missing == 0:
            return 1.0

        return explained_missing / total_with_missing