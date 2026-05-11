from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field

from algorithm.cloudmatch.agent.pipeline import SearchPipeline
from algorithm.cloudmatch.agent.user_response_formatter import format_user_response
from algorithm.cloudmatch.core.constants import PRICING_ITEMS_PER_SERVICE_LIMIT
from algorithm.cloudmatch.data.pricing_repository import PricingRepository
from algorithm.cloudmatch.data.repositories import DataRepository
from algorithm.cloudmatch.schemas.pricing import ServicePricingItem
from algorithm.cloudmatch.schemas.provider import Provider
from algorithm.cloudmatch.schemas.ranking import RankingResult, SearchResponse
from algorithm.cloudmatch.schemas.service import Service


class EmptySearchQueryError(ValueError):
    """Raised when the frontend sends an empty search query."""


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    with_explanation: bool = True
    include_debug: bool = False


class PricingItemView(BaseModel):
    item_name: str
    item_type: str
    price_rub: float | None = None
    price_unit: str | None = None
    billing_period: str | None = None
    region: str | None = None
    source_url: str | None = None


class SearchResultView(BaseModel):
    rank: int
    solution_component: str | None = None
    solution_component_reason: str | None = None
    solution_component_rank: int | None = None
    service_id: str
    service_name: str
    provider_id: str
    provider_name: str
    category: str
    description: str
    regions: list[str]
    service_url: str
    source_url: str
    pricing_model: str | None = None
    support_level: str | None = None
    price_from_rub: float | None = None
    price_unit: str | None = None
    selected_pricing_items: list[PricingItemView] = Field(default_factory=list)
    matched_entities: dict[str, Any] = Field(default_factory=dict)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    explanation: str | None = None
    final_score: float | None = None


class SearchApiResponse(BaseModel):
    query: str
    summary: str | None = None
    answer: str
    structured_query: dict[str, Any]
    results: list[SearchResultView]
    debug: dict[str, Any] | None = None


class ProviderView(BaseModel):
    provider_id: str
    name: str
    base_platform: str | None = None
    is_152fz_compliant: bool
    regions: list[str]
    source_url: str


class ServiceView(BaseModel):
    service_id: str
    provider_id: str
    provider_name: str
    name: str
    category: str
    description: str
    regions: list[str]
    price_from_rub: float | None = None
    price_unit: str | None = None
    service_url: str


class CatalogResponse(BaseModel):
    providers_count: int
    services_count: int
    providers: list[ProviderView]
    services: list[ServiceView]


class CatalogServiceCard(BaseModel):
    service_id: str
    provider_id: str
    provider_name: str
    name: str
    category: str
    description: str
    tech_stack_tags: list[str] = Field(default_factory=list)
    use_case_tags: list[str] = Field(default_factory=list)
    compliance_tags: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    pricing_model: str | None = None
    support_level: str | None = None
    price_from_rub: float | None = None
    price_unit: str | None = None
    service_url: str
    source_url: str
    pricing_items_count: int
    pricing_items: list[PricingItemView] = Field(default_factory=list)


class CatalogServicesResponse(BaseModel):
    total: int
    limit: int
    offset: int
    services: list[CatalogServiceCard]


@lru_cache(maxsize=1)
def get_search_pipeline() -> SearchPipeline:
    """
    Creates the heavy search pipeline once and reuses it between requests.

    The pipeline loads normalized data, embeddings and LLM clients, so creating
    it per request would make the website feel much slower.
    """

    return SearchPipeline()


@lru_cache(maxsize=1)
def get_data_repository() -> DataRepository:
    return DataRepository()


@lru_cache(maxsize=1)
def get_pricing_repository() -> PricingRepository:
    return PricingRepository()


def normalize_search_query(query: str) -> str:
    normalized_query = query.strip()

    if not normalized_query:
        raise EmptySearchQueryError("Search query must not be empty.")

    return normalized_query


def search_cloud_services(
    query: str,
    with_explanation: bool = True,
    include_debug: bool = False,
    pipeline: SearchPipeline | None = None,
    data_repository: DataRepository | None = None,
) -> SearchApiResponse:
    """
    Backend function for the website search form.

    It validates the incoming text, runs the existing terminal pipeline and
    converts the rich internal models into stable JSON cards for the frontend.
    """

    normalized_query = normalize_search_query(query)
    active_pipeline = pipeline or get_search_pipeline()
    active_data_repository = data_repository or get_data_repository()

    search_response = active_pipeline.search(
        user_query=normalized_query,
        with_explanation=with_explanation,
    )

    return build_search_api_response(
        response=search_response,
        data_repository=active_data_repository,
        include_debug=include_debug,
    )


def build_search_api_response(
    response: SearchResponse,
    data_repository: DataRepository,
    include_debug: bool = False,
) -> SearchApiResponse:
    answer = format_user_response(response, data_repository)

    return SearchApiResponse(
        query=response.query,
        summary=response.summary,
        answer=answer,
        structured_query=response.structured_query,
        results=[
            build_search_result_view(result, data_repository, include_debug=include_debug)
            for result in response.results
        ],
        debug=response.model_dump() if include_debug else None,
    )


def build_search_result_view(
    result: RankingResult,
    data_repository: DataRepository,
    include_debug: bool = False,
) -> SearchResultView:
    service = result.service
    provider = data_repository.providers_by_id.get(service.provider_id)
    provider_name = provider.name if provider else service.provider_id

    return SearchResultView(
        rank=result.rank,
        solution_component=result.solution_component,
        solution_component_reason=result.solution_component_reason,
        solution_component_rank=result.solution_component_rank,
        service_id=service.service_id,
        service_name=service.name,
        provider_id=service.provider_id,
        provider_name=provider_name,
        category=service.category,
        description=service.description,
        regions=service.regions,
        service_url=service.service_url,
        source_url=service.source_url,
        pricing_model=service.pricing_model,
        support_level=service.support_level,
        price_from_rub=result.price_summary.price_from_rub,
        price_unit=result.price_summary.price_unit,
        selected_pricing_items=[
            PricingItemView(
                item_name=item.item_name,
                item_type=item.item_type,
                price_rub=item.price_rub,
                price_unit=item.price_unit,
                billing_period=item.billing_period,
                region=item.region,
                source_url=item.source_url,
            )
            for item in result.selected_pricing_items
        ],
        matched_entities=result.matched_entities.model_dump(),
        score_breakdown=result.score_breakdown.model_dump() if include_debug else {},
        explanation=result.explanation,
        final_score=result.score_breakdown.final_score if include_debug else None,
    )


def get_catalog(data_repository: DataRepository | None = None) -> CatalogResponse:
    active_data_repository = data_repository or get_data_repository()

    providers = [
        ProviderView(
            provider_id=provider.provider_id,
            name=provider.name,
            base_platform=provider.base_platform,
            is_152fz_compliant=provider.is_152fz_compliant,
            regions=provider.regions,
            source_url=provider.source_url,
        )
        for provider in active_data_repository.providers
    ]

    services = [
        build_service_view(service, active_data_repository)
        for service in active_data_repository.services
    ]

    return CatalogResponse(
        providers_count=len(providers),
        services_count=len(services),
        providers=providers,
        services=services,
    )


def list_catalog_services(
    limit: int = 30,
    offset: int = 0,
    pricing_limit: int = PRICING_ITEMS_PER_SERVICE_LIMIT,
    data_repository: DataRepository | None = None,
    pricing_repository: PricingRepository | None = None,
) -> CatalogServicesResponse:
    active_data_repository = data_repository or get_data_repository()
    active_pricing_repository = pricing_repository or get_pricing_repository()
    safe_limit = max(1, limit)
    safe_offset = max(0, offset)
    safe_pricing_limit = max(0, pricing_limit)

    cards = [
        build_catalog_service_card(
            service=service,
            provider=active_data_repository.providers_by_id.get(service.provider_id),
            pricing_items=active_pricing_repository.get_items_for_service(service.service_id),
            pricing_limit=safe_pricing_limit,
        )
        for service in active_data_repository.services
    ]
    cards.sort(key=build_catalog_sort_key)
    paginated_cards = cards[safe_offset : safe_offset + safe_limit]

    return CatalogServicesResponse(
        total=len(cards),
        limit=safe_limit,
        offset=safe_offset,
        services=paginated_cards,
    )


def get_catalog_service_details(
    service_id: str,
    pricing_limit: int = 50,
    data_repository: DataRepository | None = None,
    pricing_repository: PricingRepository | None = None,
) -> CatalogServiceCard:
    active_data_repository = data_repository or get_data_repository()
    active_pricing_repository = pricing_repository or get_pricing_repository()
    service = next(
        (
            item
            for item in active_data_repository.services
            if item.service_id == service_id
        ),
        None,
    )

    if service is None:
        raise LookupError(f"Service not found: {service_id}")

    provider = active_data_repository.providers_by_id.get(service.provider_id)
    pricing_items = active_pricing_repository.get_items_for_service(service.service_id)

    return build_catalog_service_card(
        service=service,
        provider=provider,
        pricing_items=pricing_items,
        pricing_limit=max(0, pricing_limit),
    )


def build_service_view(
    service: Service,
    data_repository: DataRepository,
) -> ServiceView:
    provider = data_repository.providers_by_id.get(service.provider_id)
    provider_name = provider.name if provider else service.provider_id

    return ServiceView(
        service_id=service.service_id,
        provider_id=service.provider_id,
        provider_name=provider_name,
        name=service.name,
        category=service.category,
        description=service.description,
        regions=service.regions,
        price_from_rub=service.price_from_rub,
        price_unit=service.price_unit,
        service_url=service.service_url,
    )


def build_catalog_service_card(
    service: Service,
    provider: Provider | None,
    pricing_items: list[ServicePricingItem],
    pricing_limit: int,
) -> CatalogServiceCard:
    provider_name = provider.name if provider else service.provider_id
    selected_pricing_items = select_catalog_pricing_items(
        pricing_items=pricing_items,
        limit=pricing_limit,
    )

    return CatalogServiceCard(
        service_id=service.service_id,
        provider_id=service.provider_id,
        provider_name=provider_name,
        name=service.name,
        category=service.category,
        description=service.description,
        tech_stack_tags=service.tech_stack_tags,
        use_case_tags=service.use_case_tags,
        compliance_tags=service.compliance_tags,
        regions=service.regions,
        pricing_model=service.pricing_model,
        support_level=service.support_level,
        price_from_rub=service.price_from_rub,
        price_unit=service.price_unit,
        service_url=service.service_url,
        source_url=service.source_url,
        pricing_items_count=len(pricing_items),
        pricing_items=[
            PricingItemView(
                item_name=item.item_name,
                item_type=item.item_type,
                price_rub=item.price_rub,
                price_unit=item.price_unit,
                billing_period=item.billing_period,
                region=item.region,
                source_url=item.source_url,
            )
            for item in selected_pricing_items
        ],
    )


def select_catalog_pricing_items(
    pricing_items: list[ServicePricingItem],
    limit: int,
) -> list[ServicePricingItem]:
    if limit <= 0:
        return []

    return sorted(pricing_items, key=pricing_sort_key)[:limit]


def build_catalog_sort_key(card: CatalogServiceCard) -> tuple[str, str, str]:
    return (card.provider_name.lower(), card.category.lower(), card.name.lower())


def pricing_sort_key(item: ServicePricingItem) -> tuple[float, str]:
    price = item.price_rub if item.price_rub is not None else float("inf")
    return (price, item.item_name.lower())
