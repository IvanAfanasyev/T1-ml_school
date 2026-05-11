from typing import Optional

from pydantic import BaseModel, Field


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
    raw_text: Optional[str] = None
    parsed_at: str

    is_synthetic: bool = False