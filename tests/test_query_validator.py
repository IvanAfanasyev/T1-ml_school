import unittest

from algorithm.cloudmatch.agent.query_validator import validate_structured_query
from algorithm.cloudmatch.schemas.query import QueryConstraints, RequiredComponent, StructuredQuery


class QueryValidatorTest(unittest.TestCase):
    def test_infers_database_and_nearest_region_for_belgorod(self) -> None:
        query = validate_structured_query(
            StructuredQuery(raw_query="база данных в Белгороде")
        )

        self.assertEqual(query.task_category, "database")
        self.assertEqual(query.intent, "setup_database")
        self.assertEqual(query.constraints.region, "Belgorod")
        self.assertEqual(query.constraints.effective_region, "Moscow")
        self.assertTrue(query.constraints.region_required)
        self.assertTrue(query.constraints.region_fallback_used)
        self.assertIn("managed_database", [
            component.component
            for component in query.required_components
        ])

    def test_preserves_real_monthly_budget_with_space_separator(self) -> None:
        query = validate_structured_query(
            StructuredQuery(
                raw_query="Бюджет на инфраструктуру до 50 000 рублей в месяц.",
                constraints=QueryConstraints(budget_max=50),
            )
        )

        self.assertEqual(query.constraints.budget_max, 50000)
        self.assertTrue(query.constraints.budget_required)

    def test_infers_components_for_composite_shop_request(self) -> None:
        query = validate_structured_query(
            StructuredQuery(
                raw_query=(
                    "Интернет-магазин: backend на Python с PostgreSQL, "
                    "хранение изображений товаров, резервное копирование базы "
                    "и быстрое масштабирование при росте нагрузки."
                ),
                tech_stack=["python", "postgresql"],
                required_components=[
                    RequiredComponent(component="managed_database", db_engine="postgresql")
                ],
            )
        )
        components = {
            component.component
            for component in query.required_components
        }

        self.assertIn("compute", components)
        self.assertIn("managed_database", components)
        self.assertIn("object_storage", components)
        self.assertIn("backup", components)
        self.assertIn("load_balancer", components)


if __name__ == "__main__":
    unittest.main()
