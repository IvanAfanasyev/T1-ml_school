import unittest
from types import SimpleNamespace

from algorithm.cloudmatch.agent.pipeline import SearchPipeline
from algorithm.cloudmatch.schemas.ranking import (
    MatchedEntities,
    PriceSummary,
    RankingResult,
    ScoreBreakdown,
)
from algorithm.cloudmatch.schemas.query import RequiredComponent, StructuredQuery
from algorithm.cloudmatch.schemas.service import Service


class SolutionBundleTest(unittest.TestCase):
    def test_component_query_keeps_only_relevant_database_tech(self) -> None:
        pipeline = SearchPipeline.__new__(SearchPipeline)
        base_query = StructuredQuery(
            raw_query="backend python postgresql storage backup",
            tech_stack=["python", "postgresql", "s3"],
            use_case=["backend", "web-hosting", "database", "object-storage", "backup"],
        )
        component = RequiredComponent(
            component="managed_database",
            db_engine="postgresql",
            reason="нужна база данных",
        )

        component_query = pipeline._build_component_query(base_query, component)

        self.assertEqual(component_query.required_components, [component])
        self.assertEqual(component_query.tech_stack, ["postgresql"])
        self.assertEqual(component_query.use_case, ["database"])

    def test_component_query_keeps_backend_tech_for_compute(self) -> None:
        pipeline = SearchPipeline.__new__(SearchPipeline)
        base_query = StructuredQuery(
            raw_query="backend python postgresql storage backup",
            tech_stack=["python", "postgresql", "s3"],
            use_case=["backend", "web-hosting", "database", "object-storage", "backup"],
        )
        component = RequiredComponent(
            component="compute",
            reason="нужна среда выполнения backend",
        )

        component_query = pipeline._build_component_query(base_query, component)

        self.assertEqual(component_query.required_components, [component])
        self.assertEqual(component_query.tech_stack, ["python"])
        self.assertEqual(component_query.use_case, ["backend", "web-hosting"])

    def test_component_results_are_flattened_by_local_rank(self) -> None:
        pipeline = SearchPipeline.__new__(SearchPipeline)
        first_backend = SimpleNamespace(rank=0, name="backend-1")
        second_backend = SimpleNamespace(rank=0, name="backend-2")
        first_database = SimpleNamespace(rank=0, name="database-1")
        second_database = SimpleNamespace(rank=0, name="database-2")

        results = pipeline._flatten_component_rank_groups(
            [
                [first_backend, second_backend],
                [first_database, second_database],
            ]
        )

        self.assertEqual(
            [result.name for result in results],
            ["backend-1", "database-1", "backend-2", "database-2"],
        )
        self.assertEqual([result.rank for result in results], [1, 2, 3, 4])

    def test_component_sort_prefers_direct_service_title_match(self) -> None:
        pipeline = SearchPipeline.__new__(SearchPipeline)
        indirect_storage = SimpleNamespace(
            service=SimpleNamespace(
                name="Scalable File Service",
                category="Cloud Storage",
                description="Сервис можно использовать для резервного копирования.",
                tech_stack_tags=[],
                use_case_tags=["backup"],
                compliance_tags=[],
            ),
            score_breakdown=SimpleNamespace(final_score=0.78),
        )
        direct_backup = SimpleNamespace(
            service=SimpleNamespace(
                name="Cloud Backup And Recovery",
                category="Cloud Storage",
                description="Резервное копирование и восстановление данных.",
                tech_stack_tags=[],
                use_case_tags=["backup"],
                compliance_tags=[],
            ),
            score_breakdown=SimpleNamespace(final_score=0.76),
        )
        component = RequiredComponent(component="backup")

        results = pipeline._sort_component_results_for_component(
            [indirect_storage, direct_backup],
            component,
        )

        self.assertIs(results[0], direct_backup)

    def test_solution_bundle_is_built_from_one_provider(self) -> None:
        pipeline = SearchPipeline.__new__(SearchPipeline)
        backend_t1 = build_result("t1-cloud", "Compute", "compute", 0.9)
        database_t1 = build_result("t1-cloud", "PostgreSQL", "managed_database", 0.8)
        backend_cloud = build_result("cloud-ru", "Server", "compute", 0.85)
        database_cloud = build_result("cloud-ru", "Database", "managed_database", 0.75)

        results = pipeline._build_single_provider_bundles(
            [
                [backend_t1, backend_cloud],
                [database_t1, database_cloud],
            ]
        )

        first_bundle = [
            result for result in results
            if result.solution_component_rank == 1
        ]

        self.assertEqual({result.service.provider_id for result in first_bundle}, {"t1-cloud"})
        self.assertEqual(
            [result.solution_component for result in first_bundle],
            ["compute", "managed_database"],
        )


def build_result(
    provider_id: str,
    name: str,
    component: str,
    score: float,
) -> RankingResult:
    service = Service(
        service_id=f"{provider_id}-{name.lower()}",
        provider_id=provider_id,
        name=name,
        category="Test",
        description="Test service",
        service_url="https://example.com",
        source_url="https://example.com",
        parsed_at="2026-05-11T00:00:00+00:00",
    )
    return RankingResult(
        rank=0,
        service=service,
        solution_component=component,
        solution_component_reason=component,
        selected_pricing_items=[],
        price_summary=PriceSummary(),
        score_breakdown=ScoreBreakdown(final_score=score),
        matched_entities=MatchedEntities(),
    )


if __name__ == "__main__":
    unittest.main()
