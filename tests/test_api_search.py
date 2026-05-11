import unittest

from backend.app.api.search import (
    EmptySearchQueryError,
    build_search_api_response,
    get_catalog_service_details,
    list_catalog_services,
    normalize_search_query,
)
from algorithm.cloudmatch.schemas.pricing import ServicePricingItem
from algorithm.cloudmatch.schemas.provider import Provider
from algorithm.cloudmatch.schemas.ranking import (
    MatchedEntities,
    PriceSummary,
    RankingResult,
    ScoreBreakdown,
    SearchResponse,
)
from algorithm.cloudmatch.schemas.service import Service


class FakeDataRepository:
    def __init__(self) -> None:
        provider = Provider(
            provider_id="selectel",
            name="Selectel",
            base_platform=None,
            is_152fz_compliant=True,
            regions=["Moscow"],
            source_url="https://example.com/provider",
            parsed_at="2026-01-01",
        )
        postgres = Service(
            service_id="managed-postgres",
            provider_id="selectel",
            name="Managed PostgreSQL",
            category="Database",
            description="Управляемая база данных PostgreSQL.",
            tech_stack_tags=["postgresql"],
            use_case_tags=["database"],
            compliance_tags=["152-FZ"],
            regions=["Moscow"],
            pricing_model="pay-as-you-go",
            price_from_rub=1200,
            price_unit="rub/month",
            support_level="standard",
            service_url="https://example.com/service",
            source_url="https://example.com/source",
            parsed_at="2026-01-01",
        )
        storage = Service(
            service_id="object-storage",
            provider_id="selectel",
            name="Object Storage",
            category="Storage",
            description="S3-совместимое объектное хранилище.",
            tech_stack_tags=["s3"],
            use_case_tags=["backup"],
            compliance_tags=["152-FZ"],
            regions=["Moscow"],
            pricing_model="pay-as-you-go",
            price_from_rub=2,
            price_unit="rub/gb/month",
            support_level="standard",
            service_url="https://example.com/storage",
            source_url="https://example.com/storage-source",
            parsed_at="2026-01-01",
        )

        self.providers = [provider]
        self.services = [postgres, storage]
        self.providers_by_id = {provider.provider_id: provider}


class FakePricingRepository:
    def __init__(self) -> None:
        self.items_by_service_id = {
            "managed-postgres": [
                ServicePricingItem(
                    pricing_item_id="price-1",
                    service_id="managed-postgres",
                    provider_id="selectel",
                    item_name="PostgreSQL Small",
                    item_type="database",
                    price_rub=1200,
                    price_unit="rub/month",
                    billing_period="month",
                    region="Moscow",
                    configuration_tags=["postgresql"],
                    source_url="https://example.com/price",
                    parsed_at="2026-01-01",
                )
            ],
            "object-storage": [
                ServicePricingItem(
                    pricing_item_id="price-2",
                    service_id="object-storage",
                    provider_id="selectel",
                    item_name="S3 storage GB",
                    item_type="storage",
                    price_rub=2,
                    price_unit="rub/gb/month",
                    billing_period="month",
                    region="Moscow",
                    configuration_tags=["s3", "storage"],
                    source_url="https://example.com/storage-price",
                    parsed_at="2026-01-01",
                )
            ],
        }

    def get_items_for_service(self, service_id: str) -> list[ServicePricingItem]:
        return self.items_by_service_id.get(service_id, [])


class ApiSearchTest(unittest.TestCase):
    def test_normalize_search_query_strips_spaces(self) -> None:
        self.assertEqual(normalize_search_query("  PostgreSQL в Москве  "), "PostgreSQL в Москве")

    def test_normalize_search_query_rejects_empty_text(self) -> None:
        with self.assertRaises(EmptySearchQueryError):
            normalize_search_query("   ")

    def test_build_search_api_response_returns_frontend_cards(self) -> None:
        service = FakeDataRepository().services[0]
        pricing_item = ServicePricingItem(
            pricing_item_id="price-1",
            service_id="managed-postgres",
            provider_id="selectel",
            item_name="PostgreSQL Small",
            item_type="database",
            price_rub=1200,
            price_unit="rub/month",
            billing_period="month",
            region="Moscow",
            configuration_tags=["postgresql"],
            source_url="https://example.com/price",
            parsed_at="2026-01-01",
        )
        response = SearchResponse(
            query="нужен postgresql",
            structured_query={"tech_stack": ["postgresql"]},
            summary="Лучший вариант найден.",
            results=[
                RankingResult(
                    rank=1,
                    service=service,
                    selected_pricing_items=[pricing_item],
                    price_summary=PriceSummary(
                        price_from_rub=1200,
                        price_unit="rub/month",
                        monthly_estimate_rub=1200,
                    ),
                    score_breakdown=ScoreBreakdown(final_score=0.91),
                    matched_entities=MatchedEntities(
                        matched_tech_stack=["postgresql"],
                        budget_status="within_budget",
                    ),
                    explanation="Сервис подходит под PostgreSQL.",
                )
            ],
        )

        api_response = build_search_api_response(
            response=response,
            data_repository=FakeDataRepository(),
            include_debug=True,
        )

        self.assertEqual(api_response.results[0].provider_name, "Selectel")
        self.assertEqual(api_response.results[0].service_name, "Managed PostgreSQL")
        self.assertEqual(api_response.results[0].price_from_rub, 1200)
        self.assertEqual(api_response.results[0].monthly_estimate_rub, 1200)
        self.assertTrue(api_response.results[0].compliance_confirmed)
        self.assertIn("152-ФЗ подтверждено", api_response.answer)
        self.assertEqual(api_response.results[0].selected_pricing_items[0].item_name, "PostgreSQL Small")
        self.assertEqual(api_response.results[0].score_breakdown["final_score"], 0.91)
        self.assertIn("## Рекомендации", api_response.answer)
        self.assertIsNotNone(api_response.debug)

    def test_build_search_api_response_hides_internal_scores_without_debug(self) -> None:
        service = FakeDataRepository().services[0]
        response = SearchResponse(
            query="нужен postgresql",
            structured_query={"tech_stack": ["postgresql"]},
            results=[
                RankingResult(
                    rank=1,
                    service=service,
                    selected_pricing_items=[],
                    price_summary=PriceSummary(),
                    score_breakdown=ScoreBreakdown(final_score=0.91),
                    matched_entities=MatchedEntities(),
                )
            ],
        )

        api_response = build_search_api_response(
            response=response,
            data_repository=FakeDataRepository(),
            include_debug=False,
        )

        self.assertEqual(api_response.results[0].score_breakdown, {})
        self.assertIsNone(api_response.results[0].final_score)

    def test_list_catalog_services_returns_cards_with_pricing(self) -> None:
        response = list_catalog_services(
            limit=10,
            data_repository=FakeDataRepository(),
            pricing_repository=FakePricingRepository(),
        )

        self.assertEqual(response.total, 2)
        self.assertEqual(response.services[0].provider_name, "Selectel")
        self.assertEqual(response.services[0].pricing_items_count, 1)

    def test_list_catalog_services_supports_pagination(self) -> None:
        response = list_catalog_services(
            limit=1,
            offset=1,
            data_repository=FakeDataRepository(),
            pricing_repository=FakePricingRepository(),
        )

        self.assertEqual(response.total, 2)
        self.assertEqual(len(response.services), 1)
        self.assertEqual(response.services[0].provider_name, "Selectel")

    def test_get_catalog_service_details_returns_one_service_with_tariffs(self) -> None:
        card = get_catalog_service_details(
            service_id="managed-postgres",
            data_repository=FakeDataRepository(),
            pricing_repository=FakePricingRepository(),
        )

        self.assertEqual(card.name, "Managed PostgreSQL")
        self.assertEqual(card.pricing_items_count, 1)
        self.assertEqual(card.pricing_items[0].price_rub, 1200)


if __name__ == "__main__":
    unittest.main()
