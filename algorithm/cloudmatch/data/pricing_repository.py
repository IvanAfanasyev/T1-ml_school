from collections import defaultdict

from algorithm.cloudmatch.core.constants import PRICING_ITEMS_FILE
from algorithm.cloudmatch.data.loaders import load_json_list
from algorithm.cloudmatch.schemas.pricing import ServicePricingItem


class PricingRepository:
    def __init__(self) -> None:
        self.pricing_items = self._load_pricing_items()
        self.items_by_service_id = self._group_by_service_id()

    def _load_pricing_items(self) -> list[ServicePricingItem]:
        raw_items = load_json_list(PRICING_ITEMS_FILE)
        return [ServicePricingItem(**item) for item in raw_items]

    def _group_by_service_id(self) -> dict[str, list[ServicePricingItem]]:
        grouped = defaultdict(list)

        for item in self.pricing_items:
            grouped[item.service_id].append(item)

        return dict(grouped)

    def get_items_for_service(self, service_id: str) -> list[ServicePricingItem]:
        return self.items_by_service_id.get(service_id, [])