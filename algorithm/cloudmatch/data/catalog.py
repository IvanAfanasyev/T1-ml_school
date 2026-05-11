from functools import lru_cache
from typing import Any

from algorithm.cloudmatch.data.repositories import DataRepository
from algorithm.cloudmatch.data.pricing_repository import PricingRepository
from algorithm.cloudmatch.geo.region_resolver import canonicalize_region


@lru_cache(maxsize=1)
def get_data_catalog() -> dict[str, list[str]]:
    """
    Собирает справочник значений из текущих JSON-файлов.

    Важно:
    этот catalog НЕ является жёстким ограничением для всех полей.

    Для чего он нужен:
    1. Подсказать LLM, какие значения уже есть в данных.
    2. Помочь LLM нормализовать похожие формулировки.
    3. Не хранить списки регионов, технологий и use_case вручную в коде.

    available_regions больше не ограничивает извлечение региона:
    пользовательский город сохраняется, а ближайший доступный регион
    выбирается отдельно в geo resolver.

    Остальные поля используем как подсказку, но не запрещаем новые значения.
    """

    data_repository = DataRepository()
    pricing_repository = PricingRepository()

    regions = set()
    categories = set()
    tech_stack_tags = set()
    use_case_tags = set()
    compliance_tags = set()
    pricing_models = set()
    support_levels = set()

    pricing_item_types = set()
    configuration_tags = set()
    billing_periods = set()

    for provider in data_repository.providers:
        regions.update(_canonical_regions(provider.regions))

    for service in data_repository.services:
        regions.update(_canonical_regions(service.regions))
        categories.add(service.category)

        tech_stack_tags.update(service.tech_stack_tags)
        use_case_tags.update(service.use_case_tags)
        compliance_tags.update(service.compliance_tags)

        if service.pricing_model:
            pricing_models.add(service.pricing_model)

        if service.support_level:
            support_levels.add(service.support_level)

    for item in pricing_repository.pricing_items:
        if item.region:
            regions.add(canonicalize_region(item.region) or item.region)

        if item.item_type:
            pricing_item_types.add(item.item_type)

        if item.billing_period:
            billing_periods.add(item.billing_period)

        configuration_tags.update(item.configuration_tags)

    return {
        "available_regions": _sorted_clean(regions),
        "available_categories": _sorted_clean(categories),
        "available_tech_stack_tags": _sorted_clean(tech_stack_tags),
        "available_use_case_tags": _sorted_clean(use_case_tags),
        "available_compliance_tags": _sorted_clean(compliance_tags),
        "available_pricing_models": _sorted_clean(pricing_models),
        "available_support_levels": _sorted_clean(support_levels),
        "available_pricing_item_types": _sorted_clean(pricing_item_types),
        "available_configuration_tags": _sorted_clean(configuration_tags),
        "available_billing_periods": _sorted_clean(billing_periods),
    }


def get_available_regions() -> list[str]:
    """
    Отдельная короткая функция для региона.

    Регионы из данных используются для выбора effective_region,
    но не запрещают пользователю указать новый город.
    """

    return get_data_catalog()["available_regions"]


def _sorted_clean(values: set[Any]) -> list[str]:
    cleaned = {
        str(value).strip()
        for value in values
        if value is not None and str(value).strip()
    }

    return sorted(cleaned)


def _canonical_regions(values: list[str]) -> set[str]:
    return {
        canonicalize_region(value) or value
        for value in values
    }
