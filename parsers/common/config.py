from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ENV_FILES = (
    PROJECT_ROOT / ".env",
    Path.cwd() / ".env",
    Path(__file__).resolve().parent / ".env",
)


class Settings(BaseSettings):
    # В .env можно писать:
    # LLM_API_KEY=...
    # LLM_BASE_URL=https://llm.api.cloud.yandex.net/v1
    # LLM_MODEL=deepseek-v3

    llm_api_key: str
    llm_base_url: str = "https://llm.api.cloud.yandex.net/v1"
    llm_model: str = "deepseek-v3"

    model_config = SettingsConfigDict(
        env_file=tuple(str(path) for path in ENV_FILES),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()


DATA_DIR = PROJECT_ROOT / "data"


def _provider_dirs(provider_id: str) -> tuple[Path, Path]:
    raw_dir = DATA_DIR / "raw" / provider_id
    normalized_dir = DATA_DIR / "normalized" / provider_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir, normalized_dir


def cloud_ru_config() -> SimpleNamespace:
    provider_id = "cloud-ru"
    raw_dir, normalized_dir = _provider_dirs(provider_id)
    return SimpleNamespace(
        PROVIDER_ID=provider_id,
        PROVIDER_NAME="Cloud.ru",
        BASE_PLATFORM="Advanced",
        COMPLIANCE_URL="https://cloud.ru/docs/overview/security-introduction/topics/compliance",
        REGIONS_URL="https://cloud.ru/docs/advanced/overview/az-and-endpoints",
        TARIFF_INDEX_URL="https://cloud.ru/documents/tariffs/advanced/services/index?source-platform=Advanced",
        DATA_DIR=DATA_DIR,
        RAW_DIR=raw_dir,
        NORMALIZED_DIR=normalized_dir,
        REQUEST_TIMEOUT=30,
        USER_AGENT="Mozilla/5.0 cloud-ru-parser/1.0 educational-mvp",
    )


def selectel_config() -> SimpleNamespace:
    provider_id = "selectel"
    raw_dir, normalized_dir = _provider_dirs(provider_id)
    return SimpleNamespace(
        PROVIDER_ID=provider_id,
        PROVIDER_NAME="Selectel",
        BASE_PLATFORM="Selectel",
        COMPLIANCE_URL="https://docs.selectel.ru/certified-data-center-segment/about/documents/",
        AVAILABILITY_URL="https://docs.selectel.ru/infrastructure/availability-matrix/",
        PRICING_URL="https://selectel.ru/prices/",
        DOCS_URL="https://docs.selectel.ru/",
        DATA_DIR=DATA_DIR,
        RAW_DIR=raw_dir,
        NORMALIZED_DIR=normalized_dir,
        REQUEST_TIMEOUT=40,
        USER_AGENT=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
    )


def t1_cloud_config() -> SimpleNamespace:
    provider_id = "t1_cloud"
    raw_dir, normalized_dir = _provider_dirs(provider_id)
    return SimpleNamespace(
        PROVIDER_ID="t1-cloud",
        PROVIDER_NAME="Т1 Облако",
        BASE_PLATFORM="OpenStack",
        BASE_URL="https://t1-cloud.ru",
        RATES_URL="https://t1-cloud.ru/documents/rates",
        CERTS_URL="https://t1-cloud.ru/about-company/licenses-and-sertificates",
        ZONES_URL="https://t1-cloud.ru/docs/article/cloud-engine-openstack/zoni-dostupnosti-i-data-tsentri",
        DOCS_URL="https://t1-cloud.ru/docs",
        DATA_DIR=DATA_DIR,
        RAW_DIR=raw_dir,
        NORMALIZED_DIR=normalized_dir,
        REQUEST_TIMEOUT=60,
        USER_AGENT=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
    )


def vk_cloud_config() -> SimpleNamespace:
    provider_id = "vk-cloud"
    raw_dir, normalized_dir = _provider_dirs(provider_id)
    return SimpleNamespace(
        PROVIDER_ID=provider_id,
        PROVIDER_NAME="VK Cloud",
        BASE_PLATFORM="VK Cloud",
        COMPLIANCE_URL="https://cloud.vk.com/docs/ru/start/legal/vk/policy-152fz",
        REGIONS_URL="https://cloud.vk.com/docs/start/concepts/architecture#az",
        PRICELIST_URL="https://cloud.vk.com/pricelist/",
        DATA_DIR=DATA_DIR,
        RAW_DIR=raw_dir,
        NORMALIZED_DIR=normalized_dir,
        REQUEST_TIMEOUT=30,
        USER_AGENT="Mozilla/5.0 vk-cloud-parser/1.0 educational-mvp",
    )
