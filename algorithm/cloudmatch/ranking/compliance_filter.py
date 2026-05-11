from algorithm.cloudmatch.core.constants import REQUIRED_COMPLIANCE_TAG
from algorithm.cloudmatch.geo.region_resolver import canonicalize_region, normalize_location_key
from algorithm.cloudmatch.schemas.provider import Provider
from algorithm.cloudmatch.schemas.service import Service


def normalize_for_compare(value: str) -> str:
    return normalize_location_key(canonicalize_region(value) or value)


def is_152fz_tag(value: str) -> bool:
    normalized = str(value).strip().lower().replace("_", "-").replace(" ", "-")
    return normalized == "152-fz" or normalized.startswith("152-fz-")


def service_has_required_compliance(
    service: Service,
    provider: Provider | None,
) -> bool:
    """
    Проверяет обязательный фильтр 152-ФЗ.

    152-ФЗ — hard filter.
    Если услуга его не проходит, она не попадает в RAG и scoring.
    """

    required_tag = normalize_for_compare(REQUIRED_COMPLIANCE_TAG)

    service_compliance_tags = {normalize_for_compare(tag) for tag in service.compliance_tags}

    if required_tag in service_compliance_tags:
        return True

    if any(is_152fz_tag(tag) for tag in service.compliance_tags):
        return True

    if provider is not None and provider.is_152fz_compliant:
        return True

    return False


def service_matches_region(
    service: Service,
    provider: Provider | None,
    region: str | None,
) -> bool:
    """
    Проверяет регион.

    Регион — hard filter только если он указан в structured_query.

    Сравнение делаем без учёта регистра.
    Это не ручная нормализация, а защита от технических различий:
    Moskva == moskva
    """

    if region is None:
        return True

    required_region = normalize_for_compare(region)

    service_regions = {
        normalize_for_compare(item)
        for item in service.regions
    }

    if required_region in service_regions:
        return True

    if provider is not None:
        provider_regions = {
            normalize_for_compare(item)
            for item in provider.regions
        }

        if required_region in provider_regions:
            return True

    return False


def apply_hard_filters(
    services: list[Service],
    providers_by_id: dict[str, Provider],
    required_region: str | None = None,
) -> list[Service]:
    """
    Применяет hard filters.

    Сейчас:
    1. 152-ФЗ;
    2. регион, если пользователь его указал.

    Технологии, use_case и остальные критерии здесь не фильтруем.
    Их учитывают RAG и scoring.
    """

    filtered_services = []

    for service in services:
        provider = providers_by_id.get(service.provider_id)

        if not service_has_required_compliance(service, provider):
            continue

        if not service_matches_region(service, provider, required_region):
            continue

        filtered_services.append(service)

    return filtered_services
