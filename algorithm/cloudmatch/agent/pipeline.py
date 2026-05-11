from algorithm.cloudmatch.agent.explainer import RankingExplainer
from algorithm.cloudmatch.agent.explanation_builder import build_explanation_payload
from algorithm.cloudmatch.agent.query_extractor import QueryExtractor
from algorithm.cloudmatch.agent.query_validator import validate_structured_query
from algorithm.cloudmatch.data.pricing_repository import PricingRepository
from algorithm.cloudmatch.data.repositories import DataRepository
from algorithm.cloudmatch.ranking.budget_matcher import (
    build_price_summary,
    calculate_budget_status_and_score,
)
from algorithm.cloudmatch.ranking.compliance_filter import apply_hard_filters
from algorithm.cloudmatch.ranking.entity_matcher import calculate_entity_match_score
from algorithm.cloudmatch.ranking.pricing_matcher import select_pricing_items_for_display
from algorithm.cloudmatch.ranking.scoring import calculate_final_score
from algorithm.cloudmatch.ranking.topk import select_top_k
from algorithm.cloudmatch.retrieval.hybrid import HybridRetriever
from algorithm.cloudmatch.schemas.query import RequiredComponent
from algorithm.cloudmatch.schemas.ranking import SearchResponse


BUNDLE_COMPONENT_RESULTS_PER_ROLE = 10


class SearchPipeline:
    """
    Главный pipeline пользовательского поиска.

    Он объединяет:
    - LLM extractor;
    - hard filters;
    - hybrid retrieval;
    - entity matching;
    - requirements matching;
    - budget matching;
    - final scoring;
    - top-3 selection;
    - LLM explanation.
    """

    def __init__(self) -> None:
        self.query_extractor = QueryExtractor()
        self.data_repository = DataRepository()
        self.pricing_repository = PricingRepository()
        self.retriever = HybridRetriever()
        self.explainer = RankingExplainer()

    def search(
        self,
        user_query: str,
        with_explanation: bool = True,
    ) -> SearchResponse:
        structured_query = self.query_extractor.extract(user_query)
        structured_query = validate_structured_query(structured_query)

        all_services = self.data_repository.get_all_services()

        results = []

        if self._is_solution_bundle_query(structured_query):
            results = self._rank_solution_bundle(
                structured_query=structured_query,
                services=all_services,
            )
        else:
            for region_filter in self._get_region_filter_candidates(structured_query):
                attempt_query = self._build_query_for_region_attempt(
                    query=structured_query,
                    effective_region=region_filter,
                )

                results = self._rank_services(
                    structured_query=attempt_query,
                    services=all_services,
                )

                if results:
                    structured_query = attempt_query
                    break

        summary = None

        is_solution_bundle = any(result.solution_component for result in results)

        if with_explanation and results and not is_solution_bundle:
            payload = build_explanation_payload(
                user_query=user_query,
                structured_query=structured_query,
                results=results,
                providers_by_id=self.data_repository.providers_by_id,
            )

            summary, explanations_by_service_id = self.explainer.explain(payload)

            for result in results:
                result.explanation = explanations_by_service_id.get(
                    result.service.service_id
                )

        return SearchResponse(
            query=user_query,
            structured_query=structured_query.model_dump(),
            results=results,
            summary=summary,
        )

    def _rank_services(
        self,
        structured_query,
        services,
        top_k=3,
    ):
        required_region = None

        if structured_query.constraints.region_required:
            required_region = structured_query.constraints.effective_region

        filtered_services = apply_hard_filters(
            services=services,
            providers_by_id=self.data_repository.providers_by_id,
            required_region=required_region,
        )

        retrieval_candidates = self.retriever.retrieve(
            query=structured_query,
            services=filtered_services,
        )

        scored_candidates = []

        for candidate in retrieval_candidates:
            service = candidate.service

            pricing_items = self.pricing_repository.get_items_for_service(
                service.service_id
            )

            price_summary = build_price_summary(
                service=service,
                pricing_items=pricing_items,
            )

            budget_status, budget_score = calculate_budget_status_and_score(
                budget_max=structured_query.constraints.budget_max,
                price_summary=price_summary,
            )

            entity_match_score, matched_entities = calculate_entity_match_score(
                query=structured_query,
                service=service,
                pricing_items=pricing_items,
                budget_score=budget_score,
                budget_status=budget_status,
            )

            final_score = calculate_final_score(
                retrieval_score=candidate.score_breakdown.retrieval_score,
                entity_match_score=entity_match_score,
            )

            selected_pricing_items = select_pricing_items_for_display(
                pricing_items=pricing_items,
                service=service,
                query=structured_query,
            )

            candidate.pricing_items = pricing_items
            candidate.selected_pricing_items = selected_pricing_items
            candidate.price_summary = price_summary
            candidate.matched_entities = matched_entities
            candidate.score_breakdown.entity_match_score = entity_match_score
            candidate.score_breakdown.final_score = final_score

            scored_candidates.append(candidate)

        return select_top_k(scored_candidates, top_k=top_k)

    def _is_solution_bundle_query(self, structured_query) -> bool:
        if structured_query.request_type == "solution_bundle":
            return True

        if structured_query.request_type == "single_service":
            return False

        components = {
            component.component
            for component in structured_query.required_components
        }
        return len(components) >= 2

    def _rank_solution_bundle(
        self,
        structured_query,
        services,
    ):
        component_result_groups = []

        for component in structured_query.required_components:
            component_query = self._build_component_query(
                base_query=structured_query,
                component=component,
            )
            component_results = []

            for region_filter in self._get_region_filter_candidates(component_query):
                attempt_query = self._build_query_for_region_attempt(
                    query=component_query,
                    effective_region=region_filter,
                )
                component_results = self._rank_services(
                    structured_query=attempt_query,
                    services=services,
                    top_k=BUNDLE_COMPONENT_RESULTS_PER_ROLE,
                )

                if component_results:
                    break

            if not component_results:
                continue

            component_results = self._sort_component_results_for_component(
                component_results=component_results,
                component=component,
            )

            for component_rank, result in enumerate(component_results, start=1):
                result.solution_component = component.component
                result.solution_component_reason = component.reason
                result.solution_component_rank = component_rank

            component_result_groups.append(component_results)

        results = self._build_single_provider_bundles(component_result_groups)

        if results:
            return results

        results = self._flatten_component_rank_groups(component_result_groups)

        if results:
            return results

        return self._rank_services(
            structured_query=structured_query,
            services=services,
        )

    def _build_component_query(
        self,
        base_query,
        component: RequiredComponent,
    ):
        component_query = base_query.model_copy(deep=True)
        component_query.required_components = [component]
        component_query.raw_query = (
            f"{base_query.raw_query}\n"
            f"Отдельный компонент решения: {component.component}. "
            f"{component.reason or ''}"
        )
        component_query.tech_stack = self._select_component_tech_stack(
            base_tech_stack=base_query.tech_stack,
            component=component,
        )
        component_query.use_case = self._select_component_use_cases(
            base_use_cases=base_query.use_case,
            component=component,
        )
        return component_query

    def _select_component_tech_stack(
        self,
        base_tech_stack: list[str],
        component: RequiredComponent,
    ) -> list[str]:
        component_name = component.component.replace("_", "-")
        database_engines = {"postgresql", "mysql", "clickhouse", "redis", "mongodb"}
        app_tech = {
            "python",
            "django",
            "fastapi",
            "flask",
            "nodejs",
            "node.js",
            "java",
            "docker",
        }

        if component_name == "managed-database":
            if component.db_engine:
                return [component.db_engine]

            return [
                tech
                for tech in base_tech_stack
                if tech in database_engines
            ]

        if component_name in {"compute", "kubernetes"}:
            return [
                tech
                for tech in base_tech_stack
                if tech in app_tech or tech == "kubernetes"
            ]

        if component_name == "object-storage":
            return [
                tech
                for tech in base_tech_stack
                if tech in {"s3", "object_storage", "object-storage"}
            ]

        return []

    def _select_component_use_cases(
        self,
        base_use_cases: list[str],
        component: RequiredComponent,
    ) -> list[str]:
        component_name = component.component.replace("_", "-")
        use_case_map = {
            "compute": {"backend", "web-hosting", "scaling"},
            "managed-database": {"database"},
            "object-storage": {"object-storage", "storage"},
            "backup": {"backup"},
            "kubernetes": {"devops", "container-orchestration"},
            "load-balancer": {"network", "scaling", "web-hosting"},
            "analytics": {"analytics", "big-data"},
            "ai-ml": {"ml", "data-science"},
        }
        allowed = use_case_map.get(component_name, set())
        selected = [
            use_case
            for use_case in base_use_cases
            if use_case in allowed
        ]

        if selected:
            return selected

        fallback = {
            "compute": ["backend"],
            "managed-database": ["database"],
            "object-storage": ["object-storage"],
            "backup": ["backup"],
            "kubernetes": ["devops"],
            "load-balancer": ["network"],
            "analytics": ["analytics"],
            "ai-ml": ["ml"],
        }
        return fallback.get(component_name, [])

    def _sort_component_results_for_component(
        self,
        component_results,
        component: RequiredComponent,
    ):
        for result in component_results:
            component_bonus = self._component_title_bonus(result, component)
            result.score_breakdown.final_score = min(
                1.0,
                result.score_breakdown.final_score + component_bonus,
            )

        return sorted(
            component_results,
            key=lambda result: result.score_breakdown.final_score,
            reverse=True,
        )

    def _component_title_bonus(
        self,
        result,
        component: RequiredComponent,
    ) -> float:
        service = result.service
        title_text = f"{service.name} {service.category}".lower()
        tag_text = " ".join(
            [
                *service.tech_stack_tags,
                *service.use_case_tags,
                *service.compliance_tags,
            ]
        ).lower()
        description_text = service.description.lower()
        terms = self._component_priority_terms(component)

        if not terms:
            return 0.0

        title_match = any(term in title_text for term in terms)
        tag_match = any(term in tag_text for term in terms)
        description_match = any(term in description_text for term in terms)

        if title_match:
            return 0.08
        if tag_match:
            return 0.03
        if description_match:
            return 0.01

        return 0.0

    def _component_priority_terms(self, component: RequiredComponent) -> list[str]:
        component_name = component.component.replace("_", "-")
        terms_by_component = {
            "backup": ["backup", "recovery", "резерв"],
            "compute": ["compute", "server", "virtual", "vm", "ecs", "сервер"],
            "load-balancer": ["load balancer", "balancer", "баланс"],
            "object-storage": ["object storage", "object", "s3", "объект"],
            "kubernetes": ["kubernetes", "k8s"],
            "analytics": ["analytics", "analytic", "аналит"],
            "ai-ml": ["ai", "ml", "machine learning"],
        }

        if component_name == "managed-database":
            terms = ["database", "база", "db"]
            if component.db_engine:
                terms.insert(0, component.db_engine.lower())
            return terms

        return terms_by_component.get(component_name, [])

    def _flatten_component_rank_groups(
        self,
        component_result_groups,
    ):
        results = []
        max_group_size = max(
            (len(group) for group in component_result_groups),
            default=0,
        )

        for component_rank in range(1, max_group_size + 1):
            for group in component_result_groups:
                if len(group) < component_rank:
                    continue

                result = group[component_rank - 1]
                result.rank = len(results) + 1
                results.append(result)

        return results

    def _build_single_provider_bundles(
        self,
        component_result_groups,
    ):
        if not component_result_groups:
            return []

        provider_ids = set(
            result.service.provider_id
            for result in component_result_groups[0]
        )

        for group in component_result_groups[1:]:
            provider_ids &= {
                result.service.provider_id
                for result in group
            }

        if not provider_ids:
            return []

        provider_bundles = []

        for provider_id in provider_ids:
            bundle_results = []

            for group in component_result_groups:
                provider_results = [
                    result
                    for result in group
                    if result.service.provider_id == provider_id
                ]

                if not provider_results:
                    break

                best_result = max(
                    provider_results,
                    key=lambda result: result.score_breakdown.final_score,
                )
                bundle_results.append(best_result)

            if len(bundle_results) != len(component_result_groups):
                continue

            provider_bundles.append(
                (
                    self._calculate_bundle_score(bundle_results),
                    provider_id,
                    bundle_results,
                )
            )

        provider_bundles.sort(
            key=lambda item: (item[0], item[1]),
            reverse=True,
        )

        results = []
        for bundle_rank, (_, _, bundle_results) in enumerate(provider_bundles[:3], start=1):
            for original_result in bundle_results:
                result = original_result.model_copy(deep=True)
                result.solution_component_rank = bundle_rank
                result.rank = len(results) + 1
                results.append(result)

        return results

    def _calculate_bundle_score(self, bundle_results) -> float:
        if not bundle_results:
            return 0.0

        score_sum = sum(
            result.score_breakdown.final_score
            for result in bundle_results
        )
        return score_sum / len(bundle_results)

    def _get_region_filter_candidates(self, structured_query) -> list[str | None]:
        constraints = structured_query.constraints

        if not constraints.region_required:
            return [None]

        candidates: list[str | None] = []

        self._add_region_candidate(candidates, constraints.effective_region)

        for nearby_region in constraints.nearby_regions:
            self._add_region_candidate(candidates, nearby_region)

        return candidates or [None]

    def _add_region_candidate(
        self,
        candidates: list[str | None],
        region: str | None,
    ) -> None:
        if region is None or region in candidates:
            return

        candidates.append(region)

    def _build_query_for_region_attempt(
        self,
        query,
        effective_region: str | None,
    ):
        attempt_query = query.model_copy(deep=True)
        constraints = attempt_query.constraints

        if not constraints.region_required:
            constraints.effective_region = None
            constraints.region_fallback_used = False
            constraints.region_fallback_reason = None
            return attempt_query

        requested_region = constraints.region
        constraints.effective_region = effective_region

        constraints.region_fallback_used = (
            requested_region is not None
            and effective_region is not None
            and requested_region != effective_region
        )

        if constraints.region_fallback_used:
            constraints.region_fallback_reason = (
                f"Для региона {requested_region} не найдено прямого "
                f"подходящего результата; выбран ближайший доступный "
                f"регион {effective_region}."
            )
        else:
            constraints.region_fallback_reason = None

        return attempt_query
