import json
from typing import Any

from algorithm.cloudmatch.data.catalog import get_data_catalog
from algorithm.cloudmatch.llm.client import LLMClient
from algorithm.cloudmatch.llm.prompts.query_extractor import (
    QUERY_EXTRACTOR_SYSTEM_PROMPT,
    build_query_extractor_user_prompt,
)
from algorithm.cloudmatch.schemas.query import StructuredQuery


class QueryExtractor:
    """
    Отвечает за извлечение структуры из пользовательского prompt.

    Логика:
    1. Получает обычный текст пользователя.
    2. Собирает data_catalog из providers/services/pricing_items.
    3. Передаёт текст и data_catalog в LLM.
    4. Получает JSON.
    5. Чистит и нормализует JSON.
    6. Превращает JSON в StructuredQuery.
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def extract(self, user_query: str) -> StructuredQuery:
        data_catalog = get_data_catalog()

        user_prompt = build_query_extractor_user_prompt(
            user_query=user_query,
            data_catalog=data_catalog,
        )

        raw_response = self.llm_client.chat(
            system_prompt=QUERY_EXTRACTOR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        parsed_json = self._parse_json(raw_response)

        normalized_json = self._normalize_llm_json(
            data=parsed_json,
            user_query=user_query,
        )

        return StructuredQuery(**normalized_json)

    def _parse_json(self, raw_response: str) -> dict[str, Any]:
        cleaned = raw_response.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned.removeprefix("```json").strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```").strip()

        if cleaned.endswith("```"):
            cleaned = cleaned.removesuffix("```").strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"LLM returned invalid JSON: {raw_response}"
            ) from error

        if not isinstance(data, dict):
            raise ValueError("LLM JSON response must be an object")

        return data

    def _normalize_llm_json(
        self,
        data: dict[str, Any],
        user_query: str,
    ) -> dict[str, Any]:
        """
        Приводит ответ LLM к формату StructuredQuery.

        Важно:
        новые технологии, use_case и requirements не удаляются.
        Мы только приводим структуру к формату, который ожидает Pydantic.
        """

        data["raw_query"] = user_query

        data["request_type"] = self._normalize_request_type(
            data.get("request_type"),
            data.get("required_components"),
        )
        data.setdefault("task_category", None)
        data.setdefault("intent", None)
        data.setdefault("tech_stack", [])
        data.setdefault("use_case", [])
        data.setdefault("required_components", [])
        data.setdefault("constraints", {})
        data.setdefault("requirements", [])
        data.setdefault("extracted_entities", [])
        data.setdefault("confidence", 0.0)

        data["tech_stack"] = [
            self._normalize_technology_value(value)
            for value in self._ensure_string_list(data.get("tech_stack"))
        ]
        data["use_case"] = self._ensure_string_list(data.get("use_case"))

        data["required_components"] = self._normalize_required_components(
            data.get("required_components")
        )

        data["constraints"] = self._normalize_constraints(
            data.get("constraints")
        )

        data["requirements"] = self._normalize_requirements(
            data.get("requirements")
        )

        data["extracted_entities"] = self._normalize_requirements(
            data.get("extracted_entities")
        )

        return data

    def _normalize_request_type(
        self,
        value: Any,
        required_components: Any,
    ) -> str:
        normalized = str(value or "").strip().lower()

        if normalized in {"solution_bundle", "bundle", "multi_service", "multi-component"}:
            return "solution_bundle"

        if normalized in {"single_service", "single", "simple"}:
            return "single_service"

        components = required_components if isinstance(required_components, list) else []
        component_names = {
            item.get("component")
            for item in components
            if isinstance(item, dict) and item.get("component")
        }

        return "solution_bundle" if len(component_names) >= 2 else "single_service"

    def _ensure_string_list(self, value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            return [value]

        if not isinstance(value, list):
            return []

        result = []

        for item in value:
            if item is None:
                continue

            result.append(str(item))

        return result

    def _normalize_required_components(self, value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []

        if isinstance(value, str):
            value = [value]

        if not isinstance(value, list):
            return []

        result = []

        for item in value:
            if isinstance(item, str):
                result.append(
                    {
                        "component": item,
                        "required": True,
                        "subtype": None,
                        "db_engine": None,
                        "reason": None,
                    }
                )
                continue

            if isinstance(item, dict):
                result.append(
                    {
                        "component": item.get("component"),
                        "required": item.get("required", True),
                        "subtype": item.get("subtype"),
                        "db_engine": self._normalize_technology_value(
                            item.get("db_engine")
                        ),
                        "reason": item.get("reason"),
                    }
                )

        return [
            item for item in result
            if item.get("component") is not None
        ]

    def _normalize_constraints(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            value = {}

        return {
            "region": value.get("region"),
            "region_required": value.get("region_required", False),
            "effective_region": value.get("effective_region"),
            "nearby_regions": self._ensure_string_list(
                value.get("nearby_regions")
            ),
            "region_fallback_used": value.get("region_fallback_used", False),
            "region_fallback_reason": value.get("region_fallback_reason"),
            "budget_min": value.get("budget_min"),
            "budget_max": value.get("budget_max"),
            "budget_required": value.get("budget_required", False),
            "budget_period": value.get("budget_period"),
            "compliance_required": True,
            "compliance_tags": ["152-FZ"],
            "additional": self._normalize_requirements(
                value.get("additional", [])
            ),
        }

    def _normalize_requirements(self, value: Any) -> list[dict[str, Any]]:
        """
        Нормализует requirements и extracted_entities.

        Поддерживает:
        1. []
        2. ["django", "postgresql"]
        3. [{"name": "support_level", "value": "24/7"}]

        Неизвестные требования не выбрасываются.
        """

        if value is None:
            return []

        if isinstance(value, str):
            value = [value]

        if not isinstance(value, list):
            return []

        result = []

        for item in value:
            if isinstance(item, str):
                result.append(
                    {
                        "name": "raw_entity",
                        "value": item,
                        "required": False,
                        "confidence": 1.0,
                        "source_text": item,
                        "reason": None,
                    }
                )
                continue

            if isinstance(item, dict):
                result.append(
                    {
                        "name": item.get("name", "raw_requirement"),
                        "value": item.get("value"),
                        "required": item.get("required", False),
                        "confidence": item.get("confidence", 1.0),
                        "source_text": item.get("source_text"),
                        "reason": item.get("reason"),
                    }
                )

        return result

    def _normalize_technology_value(self, value: Any) -> str | None:
        if value is None:
            return None

        normalized = str(value).strip().lower().replace("ё", "е")

        aliases = {
            "postgres": "postgresql",
            "постгрес": "postgresql",
            "постгре": "postgresql",
            "постгрис": "postgresql",
            "постгрискл": "postgresql",
            "посгрискл": "postgresql",
            "посгрес": "postgresql",
            "посгрескл": "postgresql",
            "майскл": "mysql",
            "мускул": "mysql",
        }

        return aliases.get(normalized, normalized)
