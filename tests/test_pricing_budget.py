import unittest

from algorithm.cloudmatch.ranking.budget_matcher import (
    build_price_summary,
    calculate_budget_status_and_score,
)
from algorithm.cloudmatch.schemas.pricing import ServicePricingItem
from algorithm.cloudmatch.schemas.service import Service


class PricingBudgetTest(unittest.TestCase):
    def test_kubernetes_price_uses_cluster_item_not_storage_gb(self) -> None:
        service = build_service(
            service_id="t1-kubernetes",
            name="Managed Service for Kubernetes",
            category="Kubernetes",
            price_from_rub=3.66,
            price_unit="руб/ГБ/мес",
        )
        items = [
            build_item(
                item_id="storage",
                service_id=service.service_id,
                name="Managed Service for Kubernetes. Дисковое пространство",
                item_type="storage",
                price=3.66,
                unit="руб/ГБ/мес",
                period="month",
            ),
            build_item(
                item_id="master",
                service_id=service.service_id,
                name="Managed Service for Kubernetes, 1 мастер-нода",
                item_type="service",
                price=2070,
                unit="руб/шт/мес",
                period="month",
            ),
        ]

        summary = build_price_summary(service=service, pricing_items=items)

        self.assertEqual(summary.price_from_rub, 2070)
        self.assertEqual(summary.monthly_estimate_rub, 2070)

    def test_tiny_budget_is_marked_as_not_matching(self) -> None:
        service = build_service(
            service_id="vk-vm",
            name="Виртуальные серверы",
            category="Cloud Compute",
            price_from_rub=820,
            price_unit="руб/мес",
        )

        summary = build_price_summary(service=service, pricing_items=[])
        status, score = calculate_budget_status_and_score(
            budget_max=1,
            price_summary=summary,
        )

        self.assertEqual(status, "over_budget")
        self.assertEqual(score, 0.0)


def build_service(
    service_id: str,
    name: str,
    category: str,
    price_from_rub: float | None,
    price_unit: str | None,
) -> Service:
    return Service(
        service_id=service_id,
        provider_id="provider",
        name=name,
        category=category,
        description="Test service",
        tech_stack_tags=["kubernetes"] if "Kubernetes" in name else [],
        use_case_tags=[],
        compliance_tags=["152-FZ"],
        regions=["Russia"],
        price_from_rub=price_from_rub,
        price_unit=price_unit,
        service_url="https://example.com",
        source_url="https://example.com",
        parsed_at="2026-05-11T00:00:00+00:00",
    )


def build_item(
    item_id: str,
    service_id: str,
    name: str,
    item_type: str,
    price: float,
    unit: str,
    period: str,
) -> ServicePricingItem:
    return ServicePricingItem(
        pricing_item_id=item_id,
        service_id=service_id,
        provider_id="provider",
        item_name=name,
        item_type=item_type,
        price_rub=price,
        price_unit=unit,
        billing_period=period,
        source_url="https://example.com",
        parsed_at="2026-05-11T00:00:00+00:00",
    )


if __name__ == "__main__":
    unittest.main()
