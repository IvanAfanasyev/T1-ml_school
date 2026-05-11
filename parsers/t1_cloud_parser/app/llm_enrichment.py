import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.llm_client import ask_llm


# =========================
# Безопасный JSON от LLM
# =========================

def extract_json_object(text: str) -> dict[str, Any]:
    """
    LLM иногда возвращает JSON внутри ```json ... ```.
    Эта функция достаёт JSON-объект из ответа.
    """
    if text is None:
        raise ValueError("LLM returned empty response")

    text = text.strip()

    # Убираем markdown-блоки
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Если вокруг JSON есть лишний текст, вырезаем первый объект
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"Cannot find JSON object in LLM response: {text[:500]}")

    json_text = text[start:end + 1]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Cannot parse LLM JSON: {error}. Response: {json_text[:500]}") from error


def clean_list(value) -> list[str]:
    if value is None:
        return []

    if not isinstance(value, list):
        return []

    result = []

    for item in value:
        if item is None:
            continue

        item = str(item).strip()

        if item and item not in result:
            result.append(item)

    return result


def safe_str(value, default=None):
    if value is None:
        return default

    value = str(value).strip()

    if not value:
        return default

    return value


# =========================
# LLM enrichment для services.json
# =========================

SERVICE_SYSTEM_PROMPT = """
Ты нормализуешь карточки облачных сервисов для прототипа маркетплейса облачных услуг.

Твоя задача — улучшить только смысловые поля:
- description
- tech_stack_tags
- use_case_tags

Нельзя придумывать факты, которых нет во входных данных.
Нельзя менять цены, compliance, provider_id, service_id, source_url.
Нельзя писать про SLA, 24/7 поддержку, сертификацию ФСТЭК, если этого нет во входных данных.

Ответ должен быть строго JSON-объектом без markdown:
{
  "description": "...",
  "tech_stack_tags": ["..."],
  "use_case_tags": ["..."]
}

Требования:
- description на русском языке, 1 короткое предложение.
- tech_stack_tags: 3-8 тегов, желательно короткие.
- use_case_tags: 3-8 тегов на английском в kebab-case.
"""


def enrich_service_with_llm(service: dict[str, Any], pricing_examples: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Улучшает смысловые поля сервиса через LLM.
    Работает только с копией словаря и возвращает обновлённый dict.

    Важно:
    Функция не меняет service_id, provider_id, цены, region, compliance и source_url.
    """
    user_prompt = {
        "service": {
            "service_id": service.get("service_id"),
            "name": service.get("name"),
            "category": service.get("category"),
            "description": service.get("description"),
            "tech_stack_tags": service.get("tech_stack_tags"),
            "use_case_tags": service.get("use_case_tags"),
            "regions": service.get("regions"),
            "compliance_tags": service.get("compliance_tags"),
            "pricing_model": service.get("pricing_model"),
            "price_from_rub": service.get("price_from_rub"),
            "price_unit": service.get("price_unit"),
        },
        "pricing_item_examples": [
            {
                "item_name": item.get("item_name"),
                "item_type": item.get("item_type"),
                "price_unit": item.get("price_unit"),
                "billing_period": item.get("billing_period"),
                "configuration_tags": item.get("configuration_tags"),
            }
            for item in pricing_examples[:12]
        ],
    }

    raw_response = ask_llm(
        system_prompt=SERVICE_SYSTEM_PROMPT,
        user_prompt=json.dumps(user_prompt, ensure_ascii=False, indent=2),
    )

    llm_data = extract_json_object(raw_response)

    updated = dict(service)

    description = safe_str(llm_data.get("description"))
    tech_stack_tags = clean_list(llm_data.get("tech_stack_tags"))
    use_case_tags = clean_list(llm_data.get("use_case_tags"))

    if description:
        updated["description"] = description

    if tech_stack_tags:
        updated["tech_stack_tags"] = tech_stack_tags

    if use_case_tags:
        updated["use_case_tags"] = use_case_tags

    return updated


# =========================
# LLM enrichment для service_pricing_items.json
# =========================

PRICING_ITEM_SYSTEM_PROMPT = """
Ты нормализуешь тарифную позицию облачного сервиса.

Твоя задача — улучшить только:
- configuration_tags

Нельзя менять item_name, item_type, цену, единицу цены, source_url, raw_text.
Нельзя придумывать факты, которых нет во входных данных.

Ответ строго JSON без markdown:
{
  "configuration_tags": ["..."]
}

Теги должны быть короткими, лучше в kebab-case.
"""


def enrich_pricing_item_with_llm(item: dict[str, Any], service: dict[str, Any]) -> dict[str, Any]:
    """
    Улучшает configuration_tags тарифной позиции через LLM.
    Обычно это не нужно для всех 375 строк, поэтому функцию лучше использовать выборочно.
    """
    user_prompt = {
        "service": {
            "service_id": service.get("service_id"),
            "name": service.get("name"),
            "category": service.get("category"),
            "tech_stack_tags": service.get("tech_stack_tags"),
            "use_case_tags": service.get("use_case_tags"),
        },
        "pricing_item": {
            "pricing_item_id": item.get("pricing_item_id"),
            "item_name": item.get("item_name"),
            "item_type": item.get("item_type"),
            "price_unit": item.get("price_unit"),
            "billing_period": item.get("billing_period"),
            "configuration_tags": item.get("configuration_tags"),
            "raw_text": item.get("raw_text"),
        },
    }

    raw_response = ask_llm(
        system_prompt=PRICING_ITEM_SYSTEM_PROMPT,
        user_prompt=json.dumps(user_prompt, ensure_ascii=False, indent=2),
    )

    llm_data = extract_json_object(raw_response)

    updated = dict(item)
    configuration_tags = clean_list(llm_data.get("configuration_tags"))

    if configuration_tags:
        updated["configuration_tags"] = configuration_tags

    return updated


# =========================
# Batch enrichment
# =========================

def group_pricing_items_by_service(pricing_items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}

    for item in pricing_items:
        service_id = item.get("service_id")
        if not service_id:
            continue

        grouped.setdefault(service_id, []).append(item)

    return grouped


def enrich_services_with_llm(
    services: list[dict[str, Any]],
    pricing_items: list[dict[str, Any]],
    enabled: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Обогащает services.json через LLM.

    Возвращает:
    - обновлённые services
    - список ошибок enrichment_errors

    Если enabled=False, просто возвращает исходные services.
    """
    if not enabled:
        return services, []

    grouped_pricing = group_pricing_items_by_service(pricing_items)

    enriched_services = []
    enrichment_errors = []

    for service in services:
        service_id = service.get("service_id")
        examples = grouped_pricing.get(service_id, [])

        try:
            enriched = enrich_service_with_llm(service, examples)
            enriched_services.append(enriched)
        except Exception as error:
            enrichment_errors.append(
                {
                    "item_type": "service",
                    "service_id": service_id,
                    "error": str(error),
                    "original_item": service,
                }
            )
            enriched_services.append(service)

    return enriched_services, enrichment_errors


def enrich_pricing_items_with_llm(
    pricing_items: list[dict[str, Any]],
    services: list[dict[str, Any]],
    enabled: bool = False,
    max_items: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Обогащает service_pricing_items.json через LLM.

    По умолчанию выключено, потому что строк 375 и это будет долго.
    Для MVP обычно достаточно enrich_services_with_llm().
    """
    if not enabled:
        return pricing_items, []

    service_by_id = {
        service.get("service_id"): service
        for service in services
        if service.get("service_id")
    }

    enriched_items = []
    enrichment_errors = []

    items_to_process = pricing_items if max_items is None else pricing_items[:max_items]
    rest_items = [] if max_items is None else pricing_items[max_items:]

    for item in items_to_process:
        service = service_by_id.get(item.get("service_id"), {})

        try:
            enriched = enrich_pricing_item_with_llm(item, service)
            enriched_items.append(enriched)
        except Exception as error:
            enrichment_errors.append(
                {
                    "item_type": "service_pricing_item",
                    "pricing_item_id": item.get("pricing_item_id"),
                    "service_id": item.get("service_id"),
                    "error": str(error),
                    "original_item": item,
                }
            )
            enriched_items.append(item)

    enriched_items.extend(rest_items)

    return enriched_items, enrichment_errors
