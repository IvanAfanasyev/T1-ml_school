from algorithm.cloudmatch.core.constants import PROVIDERS_FILE, SERVICES_FILE
from algorithm.cloudmatch.data.loaders import load_json_list
from algorithm.cloudmatch.schemas.provider import Provider
from algorithm.cloudmatch.schemas.service import Service


class DataRepository:
    def __init__(self) -> None:
        self.providers = self._load_providers()
        self.services = self._load_services()

        self.providers_by_id = {
            provider.provider_id: provider for provider in self.providers
        }

    def _load_providers(self) -> list[Provider]:
        raw_items = load_json_list(PROVIDERS_FILE)
        return [Provider(**item) for item in raw_items]

    def _load_services(self) -> list[Service]:
        raw_items = load_json_list(SERVICES_FILE)
        return [Service(**item) for item in raw_items]

    def get_provider_by_id(self, provider_id: str) -> Provider | None:
        return self.providers_by_id.get(provider_id)

    def get_all_services(self) -> list[Service]:
        return self.services