from algorithm.cloudmatch.ranking.pricing_matcher import (
    canonical,
    is_compute_service,
    is_kubernetes_service,
    is_main_pricing_item_for_service,
    select_database_component_items,
    normalize,
)
from algorithm.cloudmatch.schemas.pricing import ServicePricingItem
from algorithm.cloudmatch.schemas.ranking import PriceSummary
from algorithm.cloudmatch.schemas.query import StructuredQuery
from algorithm.cloudmatch.schemas.service import Service


DEFAULT_BUDGET_PERIOD = "month"
PERIOD_DAYS = {
    "hour": 1 / 24,
    "day": 1,
    "week": 7,
    "month": 31,
}
PERIOD_LABELS = {
    "hour": "час",
    "day": "день",
    "week": "нед",
    "month": "мес",
}


def has_positive_price(value: float | None) -> bool:
    return value is not None and value > 0


def is_service_price_usable(
    service: Service,
    query: StructuredQuery | None = None) -> bool:
    """
    Проверяет, можно ли использовать service.price_from_rub
    как стартовую цену услуги.

    В реальных данных price_from_rub может быть выбран из storage/backup строки.
    Для database-сервисов цена 1 руб/ГБ/мес не является стартовой ценой PostgreSQL.
    """

    if not has_positive_price(service.price_from_rub):
        return False

    price_source = normalize(getattr(service, "price_source", None))
    price_unit = normalize(service.price_unit)
    category = canonical(service.category)

    if price_source == "none":
        return False

    if category in {"database", "managed-database", "databases"}:
        # Цена за ГБ почти наверняка относится к storage/backup,
        # а не к базовой стоимости managed database.
        if "гб" in price_unit or "gb" in price_unit:
            return False

        # Слишком маленькая цена для managed database обычно означает,
        # что parser выбрал вспомогательную строку.
        if service.price_from_rub is not None and service.price_from_rub < 100:
            return False
    
    if is_kubernetes_service(service) or is_compute_service(service):
        if "гб" in price_unit or "gb" in price_unit:
            return False

        if service.price_from_rub is not None and service.price_from_rub < 10:
            return False


    return True


def normalize_budget_period(period: str | None) -> str:
    normalized = normalize(period)

    if normalized in {"hour", "час", "hourly"}:
        return "hour"

    if normalized in {"day", "день", "daily"}:
        return "day"

    if normalized in {"week", "неделя", "нед", "weekly"}:
        return "week"

    return "month"


def infer_source_period(price_unit: str | None, billing_period: str | None = None) -> str:
    unit = normalize(price_unit)
    period = normalize(billing_period)

    if period in {"minute", "min"} or "minute" in unit or "мин" in unit:
        return "minute"

    if period == "hour" or "/час" in unit or "hour" in unit:
        return "hour"

    if period == "day" or "/день" in unit or "/сут" in unit or "daily" in unit:
        return "day"

    if period == "week" or "/нед" in unit or "weekly" in unit:
        return "week"

    return "month"


def period_days(period: str | None) -> float:
    return PERIOD_DAYS[normalize_budget_period(period)]


def estimate_price_for_period(
    price_rub: float | None,
    price_unit: str | None,
    billing_period: str | None = None,
    quantity: float | None = None,
    target_period: str | None = None,
) -> float | None:
    if not has_positive_price(price_rub):
        return None

    multiplier = quantity if quantity is not None and quantity > 0 else 1
    source_period = infer_source_period(
        price_unit=price_unit,
        billing_period=billing_period,
    )
    target_days = period_days(target_period)

    if source_period == "minute":
        return price_rub * 60 * 24 * target_days * multiplier

    if source_period == "hour":
        return price_rub * 24 * target_days * multiplier

    if source_period == "day":
        return price_rub * target_days * multiplier

    if source_period == "week":
        return price_rub * (target_days / 7) * multiplier

    return price_rub * (target_days / PERIOD_DAYS["month"]) * multiplier


def estimate_monthly_price(
    price_rub: float | None,
    price_unit: str | None,
    billing_period: str | None = None,
    quantity: float | None = None,
) -> float | None:
    return estimate_price_for_period(
        price_rub=price_rub,
        price_unit=price_unit,
        billing_period=billing_period,
        quantity=quantity,
        target_period="month",
    )


def get_requested_budget_period(query: StructuredQuery | None) -> str:
    if query is None:
        return DEFAULT_BUDGET_PERIOD

    if query.constraints.budget_period:
        return normalize_budget_period(query.constraints.budget_period)

    for requirement in [*query.requirements, *query.constraints.additional]:
        if canonical(requirement.name) in {"budget-period", "period"}:
            return normalize_budget_period(str(requirement.value))

    return DEFAULT_BUDGET_PERIOD


def get_requested_storage_gb(query: StructuredQuery | None) -> float | None:
    if query is None:
        return None

    requirements = [
        *query.requirements,
        *query.constraints.additional,
    ]

    for requirement in requirements:
        name = canonical(requirement.name)
        if name in {"storage-gb", "storage-capacity-gb", "capacity-gb"}:
            try:
                value = float(requirement.value)
            except (TypeError, ValueError):
                return None

            return value if value > 0 else None

    return None


def should_multiply_by_storage_amount(
    price_unit: str | None,
    query: StructuredQuery | None,
) -> bool:
    unit = normalize(price_unit)
    return get_requested_storage_gb(query) is not None and (
        "гб" in unit or "gb" in unit
    )


def build_storage_amount_unit(
    base_price: float,
    base_unit: str | None,
    storage_gb: float,
    target_period: str = "month",
) -> str:
    amount = int(storage_gb) if storage_gb.is_integer() else storage_gb
    period_label = PERIOD_LABELS[normalize_budget_period(target_period)]
    return f"руб/{period_label} за {amount} ГБ ({base_price:g} {base_unit})"


def build_database_component_price_summary(
    pricing_items: list[ServicePricingItem],
    target_period: str = "month",
) -> PriceSummary | None:
    component_items = select_database_component_items(
        pricing_items=pricing_items,
        limit=3,
    )

    if len(component_items) < 2:
        return None

    monthly_values = [
        estimate_monthly_price(
            price_rub=item.price_rub,
            price_unit=item.price_unit,
            billing_period=item.billing_period,
        )
        for item in component_items
    ]

    if any(value is None for value in monthly_values):
        return None

    monthly_total = sum(value or 0 for value in monthly_values)
    period_values = [
        estimate_price_for_period(
            price_rub=item.price_rub,
            price_unit=item.price_unit,
            billing_period=item.billing_period,
            target_period=target_period,
        )
        for item in component_items
    ]

    if any(value is None for value in period_values):
        return None

    period_total = sum(value or 0 for value in period_values)
    period_label = PERIOD_LABELS[normalize_budget_period(target_period)]

    return PriceSummary(
        price_from_rub=period_total,
        price_unit=f"руб/{period_label}, минимальная оценка: CPU + RAM + диск",
        monthly_estimate_rub=monthly_total,
        period_estimate_rub=period_total,
        estimate_period=normalize_budget_period(target_period),
        source="database_component_estimate",
    )


def build_price_summary(
    service: Service,
    pricing_items: list[ServicePricingItem],
    query: StructuredQuery | None = None,
) -> PriceSummary:
    """
    Строит краткую цену услуги.

    Логика:
    1. Берём service.price_from_rub только если он выглядит как цена услуги.
    2. Иначе ищем main pricing item.
    3. Если нормальной цены нет — возвращаем price_unknown.
    """

    target_period = get_requested_budget_period(query)

    if is_service_price_usable(service, query=query):
        storage_gb = get_requested_storage_gb(query)
        multiply_by_storage = should_multiply_by_storage_amount(
            price_unit=service.price_unit,
            query=query,
        )
        display_price = service.price_from_rub
        display_unit = service.price_unit
        monthly_estimate = estimate_monthly_price(
            price_rub=service.price_from_rub,
            price_unit=service.price_unit,
            quantity=storage_gb if multiply_by_storage else None,
        )
        period_estimate = estimate_price_for_period(
            price_rub=service.price_from_rub,
            price_unit=service.price_unit,
            quantity=storage_gb if multiply_by_storage else None,
            target_period=target_period,
        )

        if multiply_by_storage and storage_gb is not None and period_estimate is not None:
            display_price = period_estimate
            display_unit = build_storage_amount_unit(
                base_price=service.price_from_rub,
                base_unit=service.price_unit,
                storage_gb=storage_gb,
                target_period=target_period,
            )

        return PriceSummary(
            price_from_rub=display_price,
            price_unit=display_unit,
            monthly_estimate_rub=monthly_estimate,
            period_estimate_rub=period_estimate,
            estimate_period=target_period,
            source="service.price_from_rub",
        )

    main_items = [
        item
        for item in pricing_items
        if is_main_pricing_item_for_service(
            item=item,
            service=service,
        )
    ]

    if main_items:
        best_item = min(
            main_items,
            key=lambda item: item.price_rub or float("inf"),
        )
        storage_gb = get_requested_storage_gb(query)
        multiply_by_storage = should_multiply_by_storage_amount(
            price_unit=best_item.price_unit,
            query=query,
        )
        monthly_estimate = estimate_monthly_price(
            price_rub=best_item.price_rub,
            price_unit=best_item.price_unit,
            billing_period=best_item.billing_period,
            quantity=storage_gb if multiply_by_storage else None,
        )
        period_estimate = estimate_price_for_period(
            price_rub=best_item.price_rub,
            price_unit=best_item.price_unit,
            billing_period=best_item.billing_period,
            quantity=storage_gb if multiply_by_storage else None,
            target_period=target_period,
        )
        display_price = best_item.price_rub
        display_unit = best_item.price_unit

        if multiply_by_storage and storage_gb is not None and period_estimate is not None:
            display_price = period_estimate
            display_unit = build_storage_amount_unit(
                base_price=best_item.price_rub,
                base_unit=best_item.price_unit,
                storage_gb=storage_gb,
                target_period=target_period,
            )

        return PriceSummary(
            price_from_rub=display_price,
            price_unit=display_unit,
            monthly_estimate_rub=monthly_estimate,
            period_estimate_rub=period_estimate,
            estimate_period=target_period,
            source=f"pricing_item:{best_item.pricing_item_id}",
        )

    if canonical(service.category) in {"database", "managed-database", "databases"}:
        database_component_summary = build_database_component_price_summary(
            pricing_items=pricing_items,
            target_period=target_period,
        )

        if database_component_summary is not None:
            return database_component_summary

    return PriceSummary(
        price_from_rub=None,
        price_unit=None,
        estimate_period=target_period,
        source="price_unknown",
    )


def calculate_budget_status_and_score(
    budget_max: float | None,
    price_summary: PriceSummary,
) -> tuple[str, float]:
    """
    Считает, укладывается ли услуга в бюджет.

    Если цена неизвестна, не убиваем сервис полностью:
    даём 0.5, потому что сервис может подходить,
    но цену надо проверить вручную.
    """

    if budget_max is None:
        return "budget_not_specified", 0.0

    comparable_price = (
        price_summary.period_estimate_rub
        if price_summary.period_estimate_rub is not None
        else price_summary.monthly_estimate_rub
        if price_summary.monthly_estimate_rub is not None
        else price_summary.price_from_rub
    )

    if comparable_price is None:
        return "price_unknown", 0.5

    if comparable_price <= budget_max:
        return "within_budget", 1.0

    if comparable_price <= budget_max * 1.2:
        return "slightly_over_budget", 0.5

    return "over_budget", 0.0
