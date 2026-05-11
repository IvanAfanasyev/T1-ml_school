import unittest

from algorithm.cloudmatch.ranking.budget_matcher import (
    build_price_summary,
    calculate_budget_status_and_score,
    estimate_monthly_price,
    estimate_price_for_period,
)
from algorithm.cloudmatch.ranking.pricing_matcher import select_pricing_items_for_display
from algorithm.cloudmatch.schemas.pricing import ServicePricingItem
from algorithm.cloudmatch.schemas.query import QueryRequirement, StructuredQuery
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

    def test_hourly_price_is_converted_to_31_day_month(self) -> None:
        self.assertAlmostEqual(
            estimate_monthly_price(
                price_rub=16.9702,
                price_unit="руб/шт/час",
                billing_period="hour",
            ),
            16.9702 * 24 * 31,
        )

    def test_hourly_price_can_be_converted_to_week(self) -> None:
        self.assertAlmostEqual(
            estimate_price_for_period(
                price_rub=10,
                price_unit="руб/шт/час",
                billing_period="hour",
                target_period="week",
            ),
            10 * 24 * 7,
        )

    def test_storage_price_uses_requested_volume(self) -> None:
        service = build_service(
            service_id="vk-storage",
            name="VK Object Storage Icebox",
            category="Cloud Storage",
            price_from_rub=1.09,
            price_unit="руб/1 Гб/мес",
        )
        query = StructuredQuery(
            raw_query="хранилище для бэкапов 500 ГБ",
            requirements=[
                QueryRequirement(
                    name="storage_gb",
                    value=500,
                    required=True,
                )
            ],
        )

        summary = build_price_summary(
            service=service,
            pricing_items=[],
            query=query,
        )

        self.assertEqual(summary.price_from_rub, 545)
        self.assertEqual(summary.monthly_estimate_rub, 545)
        self.assertIn("500 ГБ", summary.price_unit or "")

    def test_storage_price_uses_requested_week_period(self) -> None:
        service = build_service(
            service_id="vk-storage",
            name="VK Object Storage Icebox",
            category="Cloud Storage",
            price_from_rub=1.09,
            price_unit="руб/1 Гб/мес",
        )
        query = StructuredQuery(
            raw_query="хранилище 500 ГБ до 200 рублей в неделю",
            requirements=[
                QueryRequirement(
                    name="storage_gb",
                    value=500,
                    required=True,
                )
            ],
        )
        query.constraints.budget_max = 200
        query.constraints.budget_period = "week"

        summary = build_price_summary(
            service=service,
            pricing_items=[],
            query=query,
        )
        status, score = calculate_budget_status_and_score(
            budget_max=query.constraints.budget_max,
            price_summary=summary,
        )

        self.assertAlmostEqual(summary.monthly_estimate_rub or 0, 545)
        self.assertAlmostEqual(summary.period_estimate_rub or 0, 545 / 31 * 7)
        self.assertEqual(summary.estimate_period, "week")
        self.assertEqual(status, "within_budget")
        self.assertEqual(score, 1.0)

    def test_database_price_uses_minimal_component_estimate(self) -> None:
        service = build_service(
            service_id="t1-postgresql",
            name="Managed Service for PostgreSQL",
            category="Database",
            price_from_rub=3.66,
            price_unit="руб/ГБ/мес",
        )
        items = [
            build_item("cpu", service.service_id, "vCPU b5", "cpu", 405.93, "руб/шт/мес", "month"),
            build_item("ram", service.service_id, "Память, RAM", "ram", 292.43, "руб/ГБ/мес", "month"),
            build_item("disk", service.service_id, "Дисковое пространство, Light", "storage", 3.66, "руб/ГБ/мес", "month"),
        ]

        summary = build_price_summary(service=service, pricing_items=items)
        display_items = select_pricing_items_for_display(
            pricing_items=items,
            service=service,
            query=StructuredQuery(raw_query="postgresql"),
        )

        self.assertAlmostEqual(summary.monthly_estimate_rub or 0, 702.02)
        self.assertEqual([item.item_type for item in display_items], ["cpu", "ram", "storage"])


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
