from typing import Optional

from pydantic import BaseModel, Field

from algorithm.cloudmatch.schemas.pricing import ServicePricingItem
from algorithm.cloudmatch.schemas.service import Service


class ScoreBreakdown(BaseModel):
    embedding_score: float = 0.0
    bm25_score: float = 0.0
    retrieval_score: float = 0.0
    entity_match_score: float = 0.0
    final_score: float = 0.0


class MatchedEntities(BaseModel):
    matched_tech_stack: list[str] = Field(default_factory=list)
    missing_tech_stack: list[str] = Field(default_factory=list)

    matched_use_case: list[str] = Field(default_factory=list)
    missing_use_case: list[str] = Field(default_factory=list)

    matched_components: list[str] = Field(default_factory=list)
    missing_components: list[str] = Field(default_factory=list)

    matched_requirements: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    requirements_score: float = 0.0

    matched_region: Optional[str] = None

    budget_status: str = "budget_not_specified"
    budget_score: float = 0.0


class PriceSummary(BaseModel):
    price_from_rub: Optional[float] = None
    price_unit: Optional[str] = None
    source: str = "unknown"


class RankingCandidate(BaseModel):
    service: Service
    pricing_items: list[ServicePricingItem] = Field(default_factory=list)
    selected_pricing_items: list[ServicePricingItem] = Field(default_factory=list)

    price_summary: PriceSummary = Field(default_factory=PriceSummary)
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    matched_entities: MatchedEntities = Field(default_factory=MatchedEntities)

    passed_filters: list[str] = Field(default_factory=list)
    failed_filters: list[str] = Field(default_factory=list)


class RankingResult(BaseModel):
    rank: int
    service: Service
    solution_component: Optional[str] = None
    solution_component_reason: Optional[str] = None
    solution_component_rank: Optional[int] = None

    selected_pricing_items: list[ServicePricingItem] = Field(default_factory=list)
    price_summary: PriceSummary

    score_breakdown: ScoreBreakdown
    matched_entities: MatchedEntities

    explanation: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    structured_query: dict
    results: list[RankingResult]
    summary: Optional[str] = None
