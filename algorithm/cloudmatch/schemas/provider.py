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
    parsed_at: str