from typing import Optional

from pydantic import BaseModel, Field


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

    service_url: str
    source_url: str
    parsed_at: str

    is_synthetic: bool = False