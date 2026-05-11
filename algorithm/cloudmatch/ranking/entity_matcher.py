from typing import Any

from algorithm.cloudmatch.schemas.pricing import ServicePricingItem
from algorithm.cloudmatch.schemas.query import QueryRequirement, StructuredQuery
from algorithm.cloudmatch.schemas.ranking import MatchedEntities
from algorithm.cloudmatch.schemas.service import Service


BASE_ENTITY_WEIGHTS = {
    "component": 0.30,
    "tech_stack": 0.25,
    "use_case": 0.15,
    "budget": 0.15,
    "requirements": 0.15,
}


COMPONENT_TO_CATEGORIES = {
    "compute": {
        "cloud-compute",
        "compute",
        "virtual-machines",
        "virtual-servers",
        "iaas",
        "servers",
    },
    "managed-database": {
        "managed-database",
        "database",
        "databases",
        "cloud-database",
        "db",
    },
    "object-storage": {
        "object-storage",
        "cloud-storage",
        "storage",
        "s3",
    },
    "backup": {
        "backup",
        "cloud-backup",
    },
    "kubernetes": {
        "kubernetes",
        "managed-kubernetes",
        "containers",
        "devops",
    },
    "network": {
        "network",
        "load-balancer",
        "cdn",
    },
    "load-balancer": {
        "network",
        "load-balancer",
        "load-balancing",
        "balancer",
        "cdn",
    },
    "security": {
        "security",
        "compliance",
    },
    "analytics": {
        "analytics",
        "bi",
        "data-analytics",
        "big-data",
    },
    "ai-ml": {
        "ai-ml",
        "ai/ml",
        "ml",
        "machine-learning",
        "data-science",
    },
}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip().lower()


def canonical(value: Any) -> str:
    """
    Приводим строки к единому виду для сравнения:
    managed_database == managed-database
    Object Storage == object-storage
    """

    return (
        normalize_text(value)
        .replace("_", "-")
        .replace(" ", "-")
    )


def normalize_list(values: list[str]) -> set[str]:
    return {
        canonical(value)
        for value in values
        if value
    }


def stringify_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, list):
        return " ".join(stringify_value(item) for item in value)

    if isinstance(value, dict):
        parts = []

        for key, item in value.items():
            parts.append(str(key))
            parts.append(stringify_value(item))

        return " ".join(parts)

    return str(value)


def calculate_list_match(
    requested_values: list[str],
    available_values: list[str],
) -> tuple[float, list[str], list[str]]:
    """
    Считает совпадение списков.

    Используем canonical-сравнение, но в matched/missing возвращаем
    значения из запроса, чтобы объяснение было понятным.
    """

    if not requested_values:
        return 0.0, [], []

    available = normalize_list(available_values)

    matched = []
    missing = []

    for requested_value in requested_values:
        requested_key = canonical(requested_value)

        if requested_key in available:
            matched.append(normalize_text(requested_value))
        else:
            missing.append(normalize_text(requested_value))

    score = len(matched) / len(requested_values)

    return score, sorted(matched), sorted(missing)


def get_service_component_matches(
    query: StructuredQuery,
    service: Service,
) -> tuple[float, list[str], list[str]]:
    requested_components = [
        component.component
        for component in query.required_components
    ]

    if not requested_components:
        return 0.0, [], []

    service_category = canonical(service.category)
    service_use_cases = normalize_list(service.use_case_tags)
    service_tech_tags = normalize_list(service.tech_stack_tags)

    matched = []
    missing = []

    for component in requested_components:
        component_key = canonical(component)
        possible_categories = COMPONENT_TO_CATEGORIES.get(component_key, set())

        category_match = service_category in possible_categories
        use_case_match = component_key in service_use_cases
        tech_tag_match = component_key in service_tech_tags

        if category_match or use_case_match or tech_tag_match:
            matched.append(component)
        else:
            missing.append(component)

    score = len(matched) / len(requested_components)

    return score, matched, missing


def infer_use_cases_from_service(service: Service) -> list[str]:
    """
    Достраивает use_case из category, name, description и tech_stack_tags.

    Это нужно для реальных данных, потому что у части сервисов use_case_tags пустые,
    хотя category явно говорит, что это Database, Backup, CDN и т.д.
    """

    values = set(service.use_case_tags)

    category = canonical(service.category)
    service_text = build_service_text_without_pricing(service)
    tech_tags = normalize_list(service.tech_stack_tags)

    if category in {"database", "managed-database", "databases"}:
        values.add("database")
        values.add("managed-database")

    if category in {"backup", "cloud-backup"}:
        values.add("backup")

    if category in {"storage", "object-storage", "cloud-storage"}:
        values.add("storage")
        values.add("object-storage")

    if category in {"cdn"}:
        values.add("cdn")
        values.add("content-delivery")
        values.add("web-acceleration")

    if category in {"devops", "kubernetes", "containers"}:
        values.add("devops")
        values.add("container-orchestration")

    if category in {"ai-ml", "ai/ml", "ml", "machine-learning"}:
        values.add("ml")
        values.add("data-science")

    if category in {"analytics", "big-data"}:
        values.add("analytics")
        values.add("big-data")

    if {"postgresql", "mysql", "clickhouse", "redis", "opensearch", "kafka"}.intersection(tech_tags):
        values.add("database")

    if {"kubernetes", "docker", "container-registry", "gitlab", "ci-cd"}.intersection(tech_tags):
        values.add("devops")

    if {"s3", "object-storage"}.intersection(tech_tags):
        values.add("object-storage")
        values.add("storage")

    if "backup" in service_text or "резервное копирование" in service_text:
        values.add("backup")

    if "cdn" in service_text:
        values.add("cdn")

    if "jupyter" in service_text or "gpu" in service_text:
        values.add("ml")
        values.add("data-science")

    return sorted(values)


def build_service_text_without_pricing(service: Service) -> str:
    parts = [
        service.service_id,
        service.provider_id,
        service.name,
        service.category,
        service.description,
        " ".join(service.tech_stack_tags),
        " ".join(service.use_case_tags),
        " ".join(service.compliance_tags),
        " ".join(service.regions),
        service.pricing_model or "",
        service.price_unit or "",
        service.support_level or "",
    ]

    service_url = getattr(service, "service_url", None)
    source_url = getattr(service, "source_url", None)

    if service_url:
        parts.append(service_url)

    if source_url:
        parts.append(source_url)

    return " ".join(part for part in parts if part).lower()


def build_service_search_text(
    service: Service,
    pricing_items: list[ServicePricingItem],
) -> str:
    parts = [
        build_service_text_without_pricing(service),
    ]

    for item in pricing_items:
        parts.extend(
            [
                item.pricing_item_id,
                item.item_name,
                item.item_type,
                item.price_unit or "",
                item.billing_period or "",
                item.region or "",
                " ".join(item.configuration_tags),
                item.raw_text or "",
            ]
        )

    return " ".join(part for part in parts if part).lower()


def requirement_label(requirement: QueryRequirement) -> str:
    value_text = stringify_value(requirement.value)

    if value_text:
        return f"{requirement.name}={value_text}"

    return requirement.name


def is_truthy_requirement(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    text = normalize_text(value)

    return text in {
        "true",
        "yes",
        "да",
        "нужен",
        "нужна",
        "required",
        "1",
    }


def match_support_level(
    requirement: QueryRequirement,
    service: Service,
) -> bool:
    expected = normalize_text(requirement.value)
    actual = normalize_text(service.support_level)

    if not expected or not actual:
        return False

    return expected == actual or expected in actual or actual in expected


def match_billing_period(
    requirement: QueryRequirement,
    pricing_items: list[ServicePricingItem],
) -> bool:
    expected = normalize_text(requirement.value)

    if not expected:
        return False

    for item in pricing_items:
        actual = normalize_text(item.billing_period)

        if expected == actual:
            return True

    return False


def match_pricing_model(
    requirement: QueryRequirement,
    service: Service,
) -> bool:
    expected = normalize_text(requirement.value)
    actual = normalize_text(service.pricing_model)

    if not expected or not actual:
        return False

    return expected == actual or expected in actual or actual in expected


def match_managed_service(
    requirement: QueryRequirement,
    service: Service,
    service_text: str,
) -> bool:
    """
    Проверяет требование managed_service=true.

    Для реальных данных важно учитывать не только русское "управляемый",
    но и английское "managed" в названии сервиса.
    """

    if not is_truthy_requirement(requirement.value):
        return True

    managed_markers = [
        "managed",
        "managed-service",
        "managed service",
        "managed-database",
        "managed database",
        "управляем",
        "управляемый",
        "управляемая",
        "управляемое",
    ]

    return any(marker in service_text for marker in managed_markers)


def match_boolean_keyword_requirement(
    requirement: QueryRequirement,
    service_text: str,
    keywords: list[str],
) -> bool:
    if not is_truthy_requirement(requirement.value):
        return True

    return any(keyword in service_text for keyword in keywords)


def match_requirement(
    requirement: QueryRequirement,
    service: Service,
    pricing_items: list[ServicePricingItem],
    service_text: str,
) -> bool:
    name = canonical(requirement.name)
    value_text = normalize_text(stringify_value(requirement.value))
    source_text = normalize_text(requirement.source_text)

    if name == "support-level":
        return match_support_level(requirement, service)

    if name == "billing-period":
        return match_billing_period(requirement, pricing_items)

    if name == "pricing-model":
        return match_pricing_model(requirement, service)

    if name == "managed-service":
        return match_managed_service(
            requirement=requirement,
            service=service,
            service_text=service_text,
        )

    if name == "gpu-required":
        return match_boolean_keyword_requirement(
            requirement=requirement,
            service_text=service_text,
            keywords=["gpu", "graphics processing unit"],
        )

    if name == "api-required":
        return match_boolean_keyword_requirement(
            requirement=requirement,
            service_text=service_text,
            keywords=["api", "gateway"],
        )

    if name == "sla-required":
        return match_boolean_keyword_requirement(
            requirement=requirement,
            service_text=service_text,
            keywords=["sla"],
        )

    if name == "high-availability":
        return match_boolean_keyword_requirement(
            requirement=requirement,
            service_text=service_text,
            keywords=[
                "high-availability",
                "high availability",
                "ha",
                "отказоустойчив",
            ],
        )

    # Fallback для новых требований:
    # ищем value/source_text/name в тексте услуги.
    # Но true/false сами по себе не ищем, это слишком шумно.
    if value_text and value_text not in {"true", "false"} and value_text in service_text:
        return True

    if source_text and source_text in service_text:
        return True

    if name and name in service_text:
        return True

    return False


def calculate_requirements_match_score(
    query: StructuredQuery,
    service: Service,
    pricing_items: list[ServicePricingItem],
) -> tuple[float, list[str], list[str]]:
    requirements = []
    requirements.extend(query.requirements)
    requirements.extend(query.constraints.additional)

    if not requirements:
        return 0.0, [], []

    service_text = build_service_search_text(
        service=service,
        pricing_items=pricing_items,
    )

    matched = []
    missing = []

    for requirement in requirements:
        label = requirement_label(requirement)

        if match_requirement(
            requirement=requirement,
            service=service,
            pricing_items=pricing_items,
            service_text=service_text,
        ):
            matched.append(label)
        else:
            missing.append(label)

    score = len(matched) / len(requirements)

    return score, matched, missing


def calculate_entity_match_score(
    query: StructuredQuery,
    service: Service,
    pricing_items: list[ServicePricingItem],
    budget_score: float,
    budget_status: str,
) -> tuple[float, MatchedEntities]:
    active_scores = {}
    active_weights = {}

    component_score, matched_components, missing_components = (
        get_service_component_matches(
            query=query,
            service=service,
        )
    )

    if query.required_components:
        active_scores["component"] = component_score
        active_weights["component"] = BASE_ENTITY_WEIGHTS["component"]

    tech_score, matched_tech, missing_tech = calculate_list_match(
        requested_values=query.tech_stack,
        available_values=service.tech_stack_tags,
    )

    if query.tech_stack:
        active_scores["tech_stack"] = tech_score
        active_weights["tech_stack"] = BASE_ENTITY_WEIGHTS["tech_stack"]

    inferred_service_use_cases = infer_use_cases_from_service(service)

    use_case_score, matched_use_case, missing_use_case = calculate_list_match(
        requested_values=query.use_case,
        available_values=inferred_service_use_cases,
    )

    if query.use_case:
        active_scores["use_case"] = use_case_score
        active_weights["use_case"] = BASE_ENTITY_WEIGHTS["use_case"]

    if query.constraints.budget_max is not None:
        active_scores["budget"] = budget_score
        active_weights["budget"] = BASE_ENTITY_WEIGHTS["budget"]

    requirements_score, matched_requirements, missing_requirements = (
        calculate_requirements_match_score(
            query=query,
            service=service,
            pricing_items=pricing_items,
        )
    )

    if query.requirements or query.constraints.additional:
        active_scores["requirements"] = requirements_score
        active_weights["requirements"] = BASE_ENTITY_WEIGHTS["requirements"]

    if not active_scores:
        entity_match_score = 0.0
    else:
        weight_sum = sum(active_weights.values())

        entity_match_score = sum(
            active_scores[name] * (active_weights[name] / weight_sum)
            for name in active_scores
        )

    matched_entities = MatchedEntities(
        matched_tech_stack=matched_tech,
        missing_tech_stack=missing_tech,
        matched_use_case=matched_use_case,
        missing_use_case=missing_use_case,
        matched_components=matched_components,
        missing_components=missing_components,
        matched_requirements=matched_requirements,
        missing_requirements=missing_requirements,
        requirements_score=requirements_score,
        matched_region=query.constraints.effective_region or query.constraints.region,
        budget_status=budget_status,
        budget_score=budget_score,
    )

    return entity_match_score, matched_entities
