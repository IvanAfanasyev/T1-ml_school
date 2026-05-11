from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Provider(BaseModel):
    provider_id: str
    name: str
    base_platform: Optional[str] = None
    is_152fz_compliant: bool = False
    regions: list[str] = Field(default_factory=list)
    api_docs_url: Optional[str] = None
    pricing_url: Optional[str] = None
    source_url: str
    parsed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Service(BaseModel):
    service_id: str
    provider_id: str

    name: str
    category: str
    description: str

    tech_stack_tags: list[str] = Field(default_factory=list)
    use_case_tags: list[str] = Field(default_factory=list)
    compliance_tags: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)

    pricing_model: Optional[str] = None
    price_from_rub: Optional[float] = None
    price_unit: Optional[str] = None
    support_level: Optional[str] = None

    service_url: Optional[str] = None
    source_url: str
    parsed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_synthetic: bool = False


class ServicePricingItem(BaseModel):
    pricing_item_id: str
    service_id: str
    provider_id: str

    item_name: str
    item_type: str

    price_rub: Optional[float] = None
    price_unit: Optional[str] = None
    billing_period: Optional[str] = None

    region: Optional[str] = None
    configuration_tags: list[str] = Field(default_factory=list)

    source_url: str
    raw_text: str

    parsed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_synthetic: bool = False


class UserTaskTemplate(BaseModel):
    id: int
    task_category: str
    tech_stack: list[str] = Field(default_factory=list)
    use_case_tags: list[str] = Field(default_factory=list)
    budget_range_rub: Optional[str] = None
    compliance_required: bool = False
    region: Optional[str] = None
    created_for_testing: bool = True


class ParseLogRecord(BaseModel):
    provider_id: str
    url: str
    parsed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str
    records_added: int = 0
    error: Optional[str] = None


class NormalizationError(BaseModel):
    item_type: str
    provider_id: str
    source_url: str
    error: str
    raw_item: dict
    parsed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
