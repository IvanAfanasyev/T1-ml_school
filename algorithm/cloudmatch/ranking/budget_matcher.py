from algorithm.cloudmatch.ranking.pricing_matcher import (
    canonical,
    is_compute_service,
    is_kubernetes_service,
    is_main_pricing_item_for_service,
    normalize,
)
from algorithm.cloudmatch.schemas.pricing import ServicePricingItem
from algorithm.cloudmatch.schemas.ranking import PriceSummary
from algorithm.cloudmatch.schemas.query import StructuredQuery
from algorithm.cloudmatch.schemas.service import Service


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


def estimate_monthly_price(
    price_rub: float | None,
    price_unit: str | None,
    billing_period: str | None = None,
) -> float | None:
    if not has_positive_price(price_rub):
        return None

    unit = normalize(price_unit)
    period = normalize(billing_period)

    if period == "hour" or "/час" in unit or "hour" in unit:
        return price_rub * 730

    if period == "minute" or "/мин" in unit or "minute" in unit:
        return price_rub * 60 * 24 * 30

    return price_rub


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

    if is_service_price_usable(service, query=query):
        return PriceSummary(
            price_from_rub=service.price_from_rub,
            price_unit=service.price_unit,
            monthly_estimate_rub=estimate_monthly_price(
                price_rub=service.price_from_rub,
                price_unit=service.price_unit,
            ),
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

        return PriceSummary(
            price_from_rub=best_item.price_rub,
            price_unit=best_item.price_unit,
            monthly_estimate_rub=estimate_monthly_price(
                price_rub=best_item.price_rub,
                price_unit=best_item.price_unit,
                billing_period=best_item.billing_period,
            ),
            source=f"pricing_item:{best_item.pricing_item_id}",
        )

    return PriceSummary(
        price_from_rub=None,
        price_unit=None,
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
        price_summary.monthly_estimate_rub
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