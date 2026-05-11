from algorithm.cloudmatch.ranking.pricing_matcher import (
    canonical,
    is_main_pricing_item_for_service,
    normalize,
)
from algorithm.cloudmatch.schemas.pricing import ServicePricingItem
from algorithm.cloudmatch.schemas.ranking import PriceSummary
from algorithm.cloudmatch.schemas.service import Service


def has_positive_price(value: float | None) -> bool:
    return value is not None and value > 0


def is_service_price_usable(service: Service) -> bool:
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

    return True


def build_price_summary(
    service: Service,
    pricing_items: list[ServicePricingItem],
) -> PriceSummary:
    """
    Строит краткую цену услуги.

    Логика:
    1. Берём service.price_from_rub только если он выглядит как цена услуги.
    2. Иначе ищем main pricing item.
    3. Если нормальной цены нет — возвращаем price_unknown.
    """

    if is_service_price_usable(service):
        return PriceSummary(
            price_from_rub=service.price_from_rub,
            price_unit=service.price_unit,
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

    if price_summary.price_from_rub is None:
        return "price_unknown", 0.5

    if price_summary.price_from_rub <= budget_max:
        return "within_budget", 1.0

    if price_summary.price_from_rub <= budget_max * 1.2:
        return "slightly_over_budget", 0.5

    return "over_budget", 0.0