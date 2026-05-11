import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from app.schemas import Provider, Service, ServicePricingItem


# =========================
# Базовые утилиты
# =========================

def now_utc():
    return datetime.now(timezone.utc)


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    value = str(value)
    value = value.replace("\n", " ")
    value = value.replace("\r", " ")
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def as_list(value: Any) -> list:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        return [value] if value.strip() else []

    return [value]


def unique_list(items: list) -> list:
    result = []

    for item in items:
        if item is None:
            continue

        if item not in result:
            result.append(item)

    return result


def normalize_tag(tag: str) -> str:
    tag = clean_text(tag).lower()
    tag = tag.replace("_", "-")
    tag = re.sub(r"\s+", "-", tag)
    tag = re.sub(r"[^a-z0-9а-яё\-]+", "-", tag)
    tag = re.sub(r"-+", "-", tag)
    return tag.strip("-")


def make_slug(text: str, max_len: int = 70) -> str:
    text = clean_text(text).lower()
    text = text.replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    return (text or "item")[:max_len].strip("-")


def short_hash(value: str, length: int = 8) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


# =========================
# Provider строго под PDF-структуру
# =========================

def normalize_regions(regions: list[str]) -> list[str]:
    """
    В целевом PDF регионы примерами указаны как Russia/Moscow.
    Для T1 оставляем Russia и Moscow, чтобы было единообразно для ранжирования.
    """
    result = []

    for region in regions:
        region = clean_text(region).lower()

        if region in {"москва", "moscow", "moskva"}:
            value = "Moscow"
        elif region in {"россия", "рф", "russia", "ru"}:
            value = "Russia"
        else:
            value = clean_text(region)

        if value and value not in result:
            result.append(value)

    if "Moscow" in result and "Russia" not in result:
        result.insert(0, "Russia")

    return result


def normalize_provider_from_metadata(raw: dict[str, Any]) -> Provider:
    source_url = raw.get("source_url") or raw.get("pricing_url") or "https://t1-cloud.ru/documents/rates"

    return Provider(
        provider_id=raw.get("provider_id", "t1-cloud"),
        name=raw.get("name") or "Т1 Облако",
        base_platform=raw.get("base_platform"),
        is_152fz_compliant=bool(raw.get("is_152fz_compliant", False)),
        regions=normalize_regions(as_list(raw.get("regions"))),
        api_docs_url=raw.get("api_docs_url"),
        pricing_url=raw.get("pricing_url"),
        source_url=source_url,
        parsed_at=raw.get("collected_at") or now_utc(),
    )


# =========================
# Справочник сервисов
# =========================

SERVICE_PROFILES = {
    "t1-cloud-compute-cloud-engine": {
        "name": "Compute Cloud Engine",
        "category": "Compute",
        "description": "Облачные вычислительные ресурсы для виртуальных машин: vCPU, RAM, образы и дисковое пространство.",
        "tech_stack_tags": ["OpenStack", "Virtual Machine", "Compute"],
        "use_case_tags": ["web-hosting", "backend", "test-stand", "iaas"],
        "service_url": None,
    },
    "t1-cloud-gpuaas-cloud-engine": {
        "name": "GPUaaS Cloud Engine",
        "category": "Compute",
        "description": "GPU-ресурсы для задач машинного обучения, ИИ и высокопроизводительных вычислений.",
        "tech_stack_tags": ["GPU", "NVIDIA", "ML"],
        "use_case_tags": ["machine-learning", "ai", "high-performance-computing"],
        "service_url": None,
    },
    "t1-cloud-compute-cloud-director": {
        "name": "Compute Cloud Director",
        "category": "Compute",
        "description": "Вычислительные ресурсы Cloud Director: CPU, vRAM, диски и сетевые компоненты.",
        "tech_stack_tags": ["VMware", "Cloud Director", "Virtual Machine"],
        "use_case_tags": ["iaas", "enterprise-infrastructure", "backend"],
        "service_url": None,
    },
    "t1-cloud-compute-cloud-director-payg": {
        "name": "Compute Cloud Director PAYG",
        "category": "Compute",
        "description": "Вычислительные ресурсы Cloud Director с тарификацией pay-as-you-go.",
        "tech_stack_tags": ["VMware", "Cloud Director", "PAYG"],
        "use_case_tags": ["iaas", "pay-as-you-go", "enterprise-infrastructure"],
        "service_url": None,
    },
    "t1-cloud-gpuaas-cloud-director": {
        "name": "GPUaaS Cloud Director",
        "category": "Compute",
        "description": "GPU-ресурсы в среде Cloud Director.",
        "tech_stack_tags": ["GPU", "NVIDIA", "Cloud Director"],
        "use_case_tags": ["machine-learning", "ai", "high-performance-computing"],
        "service_url": None,
    },
    "t1-cloud-object-storage-s3": {
        "name": "Object Storage S3",
        "category": "Storage",
        "description": "S3-совместимое объектное хранилище для файлов, резервных копий, логов и медиа.",
        "tech_stack_tags": ["S3", "API", "Object Storage"],
        "use_case_tags": ["backup", "media-storage", "static-hosting", "data-lake"],
        "service_url": None,
    },
    "t1-cloud-backup": {
        "name": "Cloud Backup",
        "category": "Backup",
        "description": "Резервное копирование виртуальных машин, серверов, рабочих станций и баз данных.",
        "tech_stack_tags": ["Backup", "Veeam", "OpenStack"],
        "use_case_tags": ["backup", "disaster-recovery", "data-protection"],
        "service_url": None,
    },
    "t1-cloud-haas": {
        "name": "Dedicated Server HaaS",
        "category": "Compute",
        "description": "Выделенные серверы в модели Hardware as a Service.",
        "tech_stack_tags": ["Bare Metal", "Dedicated Server"],
        "use_case_tags": ["highload", "dedicated-infrastructure", "enterprise-infrastructure"],
        "service_url": None,
    },
    "t1-cloud-network-services": {
        "name": "Network Services",
        "category": "Network",
        "description": "Сетевые услуги: публичные IP-адреса, интернет-доступ и дополнительные сетевые опции.",
        "tech_stack_tags": ["Network", "IP", "Internet"],
        "use_case_tags": ["networking", "web-hosting", "traffic-delivery"],
        "service_url": None,
    },
    "t1-cloud-cdn": {
        "name": "Cloud CDN",
        "category": "Network",
        "description": "CDN для доставки контента, обработки трафика, запросов и дополнительных функций.",
        "tech_stack_tags": ["CDN", "HTTP", "Content Delivery"],
        "use_case_tags": ["content-delivery", "web-hosting", "highload"],
        "service_url": None,
    },
    "t1-cloud-microsoft-licenses": {
        "name": "Microsoft Licenses",
        "category": "Other",
        "description": "Программные услуги на базе лицензий Microsoft.",
        "tech_stack_tags": ["Microsoft", "Windows", "SQL Server"],
        "use_case_tags": ["software-license", "enterprise-software"],
        "service_url": None,
    },
    "t1-cloud-astra-linux-licenses": {
        "name": "Astra Linux Licenses",
        "category": "Other",
        "description": "Программные услуги на базе лицензий Astra Linux.",
        "tech_stack_tags": ["Linux", "Astra Linux"],
        "use_case_tags": ["software-license", "operating-system"],
        "service_url": None,
    },
    "t1-cloud-alt-linux-licenses": {
        "name": "Alt Linux Licenses",
        "category": "Other",
        "description": "Программные услуги на базе лицензий Альт Сервер.",
        "tech_stack_tags": ["Linux", "Alt Linux"],
        "use_case_tags": ["software-license", "operating-system"],
        "service_url": None,
    },
    "t1-cloud-redos-licenses": {
        "name": "RED OS Licenses",
        "category": "Other",
        "description": "Программные услуги на базе лицензий РЕД ОС.",
        "tech_stack_tags": ["Linux", "RED OS"],
        "use_case_tags": ["software-license", "operating-system"],
        "service_url": None,
    },
    "t1-cloud-disk": {
        "name": "T1 Disk",
        "category": "Storage",
        "description": "Файловое облачное хранилище Т1 Диск.",
        "tech_stack_tags": ["Cloud Disk", "File Storage"],
        "use_case_tags": ["file-storage", "collaboration", "data-storage"],
        "service_url": None,
    },
    "t1-cloud-managed-kubernetes": {
        "name": "Managed Service for Kubernetes",
        "category": "Kubernetes",
        "description": "Управляемый Kubernetes для контейнеризированных приложений.",
        "tech_stack_tags": ["Kubernetes", "Docker", "Containers"],
        "use_case_tags": ["microservices", "devops", "container-orchestration"],
        "service_url": None,
    },
    "t1-cloud-postgresql": {
        "name": "Managed Service for PostgreSQL",
        "category": "Database",
        "description": "Управляемая база данных PostgreSQL для backend-приложений и хранения структурированных данных.",
        "tech_stack_tags": ["PostgreSQL", "SQL", "Database"],
        "use_case_tags": ["backend", "database", "data-storage"],
        "service_url": None,
    },
    "t1-cloud-inmemorydb": {
        "name": "Managed Service for InmemoryDB",
        "category": "Database",
        "description": "Управляемое in-memory хранилище данных для кэша и высоконагруженных приложений.",
        "tech_stack_tags": ["Redis", "In-Memory", "Database"],
        "use_case_tags": ["cache", "backend", "highload"],
        "service_url": None,
    },
    "t1-cloud-documentdb": {
        "name": "Managed Service for DocumentDB",
        "category": "Database",
        "description": "Управляемая документная база данных для хранения неструктурированных и JSON-подобных данных.",
        "tech_stack_tags": ["DocumentDB", "NoSQL", "Database"],
        "use_case_tags": ["database", "backend", "document-storage"],
        "service_url": None,
    },
    "t1-cloud-clickhouse": {
        "name": "Managed Service for ClickHouse",
        "category": "Analytics",
        "description": "Управляемая аналитическая база данных ClickHouse для OLAP и обработки больших объемов данных.",
        "tech_stack_tags": ["ClickHouse", "OLAP", "Database"],
        "use_case_tags": ["analytics", "data-processing", "database"],
        "service_url": None,
    },
    "t1-cloud-mysql": {
        "name": "Managed Service for MySQL",
        "category": "Database",
        "description": "Управляемая база данных MySQL для веб-приложений и backend-сервисов.",
        "tech_stack_tags": ["MySQL", "SQL", "Database"],
        "use_case_tags": ["backend", "database", "web-app"],
        "service_url": None,
    },
    "t1-cloud-opensearch": {
        "name": "Managed Service for OpenSearch",
        "category": "Analytics",
        "description": "Управляемый OpenSearch для поиска, аналитики и работы с логами.",
        "tech_stack_tags": ["OpenSearch", "Search", "Logs"],
        "use_case_tags": ["search", "monitoring", "analytics"],
        "service_url": None,
    },
    "t1-cloud-kafka": {
        "name": "Managed Service for Kafka",
        "category": "Other",
        "description": "Управляемый Kafka для потоковой обработки событий.",
        "tech_stack_tags": ["Kafka", "Streaming", "Message Broker"],
        "use_case_tags": ["event-streaming", "backend", "microservices"],
        "service_url": None,
    },
    "t1-cloud-rabbitmq": {
        "name": "Managed Service for RabbitMQ",
        "category": "Other",
        "description": "Управляемый RabbitMQ для очередей сообщений.",
        "tech_stack_tags": ["RabbitMQ", "Queue", "Message Broker"],
        "use_case_tags": ["message-queue", "backend", "microservices"],
        "service_url": None,
    },
    "t1-cloud-ml-hub": {
        "name": "ML Hub",
        "category": "Analytics",
        "description": "ML Hub для задач машинного обучения и работы с моделями.",
        "tech_stack_tags": ["ML", "AI", "Machine Learning"],
        "use_case_tags": ["machine-learning", "ai", "data-science"],
        "service_url": None,
    },
    "t1-cloud-container-registry": {
        "name": "Repository for Containers",
        "category": "Kubernetes",
        "description": "Репозиторий контейнерных образов для DevOps и CI/CD-процессов.",
        "tech_stack_tags": ["Docker", "Container Registry", "Containers"],
        "use_case_tags": ["devops", "ci-cd", "container-delivery"],
        "service_url": None,
    },
    "t1-cloud-gitlab": {
        "name": "Managed Service for GitLab",
        "category": "Other",
        "description": "Управляемый GitLab для хранения кода и CI/CD.",
        "tech_stack_tags": ["GitLab", "Git", "CI/CD"],
        "use_case_tags": ["devops", "source-code", "ci-cd"],
        "service_url": None,
    },
    "t1-cloud-network-load-balancer": {
        "name": "Network Load Balancer",
        "category": "Network",
        "description": "Балансировщик сетевой нагрузки для распределения трафика между сервисами.",
        "tech_stack_tags": ["Load Balancer", "Network"],
        "use_case_tags": ["load-balancing", "highload", "web-hosting"],
        "service_url": None,
    },
    "t1-cloud-dns": {
        "name": "CloudDNS",
        "category": "Network",
        "description": "DNS-сервис для управления доменными зонами и DNS-записями.",
        "tech_stack_tags": ["DNS", "Network"],
        "use_case_tags": ["dns-management", "networking", "web-hosting"],
        "service_url": None,
    },
    "t1-cloud-kubernetes-as-a-service": {
        "name": "Kubernetes as a Service",
        "category": "Kubernetes",
        "description": "Kubernetes as a Service для запуска контейнеризированных приложений.",
        "tech_stack_tags": ["Kubernetes", "Containers"],
        "use_case_tags": ["container-orchestration", "microservices", "devops"],
        "service_url": None,
    },
    "t1-cloud-bi-platform": {
        "name": "BI Platform T1 Cloud",
        "category": "Analytics",
        "description": "Платформа бизнес-аналитики T1 Cloud для отчетности и анализа данных.",
        "tech_stack_tags": ["BI", "Analytics"],
        "use_case_tags": ["analytics", "reports", "business-intelligence"],
        "service_url": None,
    },
    "t1-cloud-scibox": {
        "name": "ML Platform SCIBOX",
        "category": "Analytics",
        "description": "ML-платформа SCIBOX для задач машинного обучения и анализа данных.",
        "tech_stack_tags": ["ML", "AI", "Machine Learning"],
        "use_case_tags": ["machine-learning", "ai", "data-science"],
        "service_url": None,
    },
    "t1-cloud-direct-connect": {
        "name": "Direct Connect",
        "category": "Network",
        "description": "Выделенное сетевое подключение Direct Connect.",
        "tech_stack_tags": ["Direct Connect", "Network"],
        "use_case_tags": ["dedicated-connectivity", "networking", "enterprise-infrastructure"],
        "service_url": None,
    },
    "t1-cloud-other": {
        "name": "Other T1 Cloud Service",
        "category": "Other",
        "description": "Прочие тарифные позиции Т1 Облако.",
        "tech_stack_tags": [],
        "use_case_tags": [],
        "service_url": None,
    },
}


# =========================
# Классификация
# =========================

def _group_text(raw_item: dict[str, Any]) -> str:
    return clean_text(raw_item.get("raw_group_name", "") + " " + " ".join(map(str, as_list(raw_item.get("raw_page_groups"))))).lower()


def detect_service_id(raw_item: dict[str, Any]) -> str:
    name = clean_text(raw_item.get("raw_tariff_name")).lower()
    group = _group_text(raw_item)

    # Важные проверки по строке раньше группы.
    if "альт" in name:
        return "t1-cloud-alt-linux-licenses"

    if "ред ос" in name or "redos" in name:
        return "t1-cloud-redos-licenses"

    if "astra" in name or "астра" in name:
        return "t1-cloud-astra-linux-licenses"

    if "объектное хранилище" in name or "s3" in name:
        return "t1-cloud-object-storage-s3"

    if any(x in name for x in ["veeam", "кибер бэкап", "резервн", "backup"]):
        return "t1-cloud-backup"

    if name.startswith("cdn") or " cdn" in name or "cdn." in name:
        return "t1-cloud-cdn"

    if "публичный ip" in name or "интернет" in name:
        return "t1-cloud-network-services"

    if re.match(r"^h\d+\s*\(", name):
        return "t1-cloud-haas"

    direct_name_rules = [
        ("kubernetes as a service", "t1-cloud-kubernetes-as-a-service"),
        ("managed service for kubernetes", "t1-cloud-managed-kubernetes"),
        ("managed service for postgresql", "t1-cloud-postgresql"),
        ("managed service for inmemorydb", "t1-cloud-inmemorydb"),
        ("managed service for documentdb", "t1-cloud-documentdb"),
        ("managed service for clickhouse", "t1-cloud-clickhouse"),
        ("managed service for mysql", "t1-cloud-mysql"),
        ("managed service for opensearch", "t1-cloud-opensearch"),
        ("managed service for kafka", "t1-cloud-kafka"),
        ("managed service for rabbitmq", "t1-cloud-rabbitmq"),
        ("managed service for gitlab", "t1-cloud-gitlab"),
        ("repository for containers", "t1-cloud-container-registry"),
        ("network load balancer", "t1-cloud-network-load-balancer"),
        ("clouddns", "t1-cloud-dns"),
        ("ml hub", "t1-cloud-ml-hub"),
        ("scibox", "t1-cloud-scibox"),
        ("direct connect", "t1-cloud-direct-connect"),
    ]

    for marker, service_id in direct_name_rules:
        if marker in name:
            return service_id

    # Проверки по группе.
    if "microsoft" in group:
        return "t1-cloud-microsoft-licenses"

    if "astra linux" in group:
        return "t1-cloud-astra-linux-licenses"

    if "альт сервер" in group:
        return "t1-cloud-alt-linux-licenses"

    if "ред ос" in group:
        return "t1-cloud-redos-licenses"

    if "т1 диск" in group:
        return "t1-cloud-disk"

    if "платформа бизнес-аналитики" in group or "glarus bi" in group:
        return "t1-cloud-bi-platform"

    if "direct connect" in group:
        return "t1-cloud-direct-connect"

    if "clouddns" in group:
        return "t1-cloud-dns"

    if "network load balancer" in group:
        return "t1-cloud-network-load-balancer"

    if "gpuaas" in group and "cloud director" in group:
        return "t1-cloud-gpuaas-cloud-director"

    if "gpuaas" in group and "cloud engine" in group:
        if any(x in name for x in ["gpu", "nvidia", "h100", "h200", "a100", "l40"]):
            return "t1-cloud-gpuaas-cloud-engine"
        return "t1-cloud-compute-cloud-engine"

    if "cloud director c тарификацией payg" in group or name.startswith("payg "):
        return "t1-cloud-compute-cloud-director-payg"

    if "compute" in group and "cloud director" in group:
        return "t1-cloud-compute-cloud-director"

    if "compute" in group and "cloud engine" in group:
        return "t1-cloud-compute-cloud-engine"

    if "сетевые услуги" in group:
        return "t1-cloud-network-services"

    if "выделенный сервер" in group or "haas" in group:
        return "t1-cloud-haas"

    if "хранение и резервное копирование" in group:
        return "t1-cloud-backup"

    return "t1-cloud-other"


def detect_item_type(raw_item: dict[str, Any], service_id: str) -> str:
    name = clean_text(raw_item.get("raw_tariff_name")).lower()
    unit = clean_text(raw_item.get("unit")).lower()

    if any(x in name for x in ["cdn трафик", "интернет", "трафик"]):
        return "traffic"

    if any(x in name for x in ["запрос", "put/post", "get/head"]):
        return "request"

    if "vcpu" in name or re.search(r"\bcpu\b", name) or "ядр" in unit:
        return "cpu"

    if "gpu" in name or "nvidia" in name:
        return "gpu"

    if "ram" in name or "vram" in name:
        return "ram"

    if any(x in name for x in ["диск", "хранилищ", "snapshot", "снимок", "backup", "резерв", "s3", "репозит"]):
        return "storage"

    if any(x in name for x in ["ip", "dns", "connect", "balancer", "маршрутизатор"]):
        return "network"

    if any(x in name for x in ["license", "лиценз", "office", "windows", "sql server", "astra", "альт", "ред ос"]):
        return "license"

    if service_id in {"t1-cloud-postgresql", "t1-cloud-mysql", "t1-cloud-clickhouse", "t1-cloud-documentdb", "t1-cloud-inmemorydb", "t1-cloud-opensearch"}:
        return "database"

    return "service"


def billing_period_from_raw(raw_item: dict[str, Any]) -> str | None:
    billing_hint = clean_text(raw_item.get("billing_hint")).lower()
    table_type = clean_text(raw_item.get("table_type")).lower()

    if raw_item.get("price_per_month_rub_no_vat") is not None:
        return "month"

    if raw_item.get("price_per_minute_rub_no_vat") is not None:
        return "minute"

    if "request" in billing_hint:
        return "request"

    if table_type == "month_only":
        return "month"

    return None


def price_and_unit_from_raw(raw_item: dict[str, Any]) -> tuple[float | None, str | None, str | None]:
    """
    Возвращает price_rub, price_unit, billing_period строго для service_pricing_items.json.
    Предпочитаем месячную цену, если она есть, потому что она удобнее для бюджета.
    """
    unit = clean_text(raw_item.get("unit"))
    month_price = raw_item.get("price_per_month_rub_no_vat")
    minute_price = raw_item.get("price_per_minute_rub_no_vat")

    if month_price is not None:
        return month_price, f"руб/{unit}/мес без НДС" if unit else "руб/мес без НДС", "month"

    if minute_price is not None:
        return minute_price, f"руб/{unit}*мин без НДС" if unit else "руб/мин без НДС", "minute"

    return None, None, billing_period_from_raw(raw_item)


def safe_item_name(raw_name: str) -> str:
    name = clean_text(raw_name)

    protected = []
    protected_patterns = [
        r"\bvCPU\s+[abg]\d\b",
        r"\bRAM\s+g\d\b",
        r"\bGPU\s+g\d\b",
        r"\bT1\b",
        r"\bS3\b",
        r"\bH\d+\b",
        r"\bH100\b",
        r"\bH200\b",
        r"\bA100\b",
        r"\bL40s\b",
        r"\bIPv4\b",
    ]

    for pattern in protected_patterns:
        def repl(match):
            token = f"__PROTECTED_{len(protected)}__"
            protected.append((token, match.group(0)))
            return token
        name = re.sub(pattern, repl, name, flags=re.IGNORECASE)

    name = re.sub(r"\bIPv41\b", "IPv4", name)
    name = re.sub(r"\s+[12]$", "", name)
    name = re.sub(r"(?<=[А-Яа-яA-Za-z\)])([12])(?=\s|$)", "", name)

    for token, original in protected:
        name = name.replace(token, original)

    return clean_text(name)


def make_pricing_item_id(raw_item: dict[str, Any], service_id: str) -> str:
    provider_id = raw_item.get("provider_id", "t1-cloud")
    raw_name = clean_text(raw_item.get("raw_tariff_name"))
    page = raw_item.get("source_page")
    table = raw_item.get("source_table_index")
    row = raw_item.get("source_row_index")

    slug = make_slug(raw_name, 55)
    digest = short_hash(f"{provider_id}|{service_id}|{page}|{table}|{row}|{raw_name}")

    return f"{service_id}-{slug}-{digest}"


def normalize_pricing_item(raw_item: dict[str, Any], provider: Provider) -> ServicePricingItem:
    service_id = detect_service_id(raw_item)
    profile = SERVICE_PROFILES.get(service_id, SERVICE_PROFILES["t1-cloud-other"])

    item_name = safe_item_name(raw_item.get("raw_tariff_name"))
    item_type = detect_item_type(raw_item, service_id)
    price_rub, price_unit, billing_period = price_and_unit_from_raw(raw_item)

    configuration_tags = [
        normalize_tag(profile["category"]),
        normalize_tag(item_type),
    ]

    for tag in profile["tech_stack_tags"]:
        configuration_tags.append(normalize_tag(tag))

    configuration_tags = unique_list([tag for tag in configuration_tags if tag])

    source_url = raw_item.get("source_file") or provider.pricing_url or provider.source_url

    return ServicePricingItem(
        pricing_item_id=make_pricing_item_id(raw_item, service_id),
        service_id=service_id,
        provider_id=provider.provider_id,
        item_name=item_name,
        item_type=item_type,
        price_rub=price_rub,
        price_unit=price_unit,
        billing_period=billing_period,
        region=provider.regions[0] if provider.regions else None,
        configuration_tags=configuration_tags,
        source_url=source_url,
        raw_text=clean_text(raw_item.get("raw_tariff_name")),
        parsed_at=now_utc(),
        is_synthetic=False,
    )


# =========================
# Services строго под PDF-структуру
# =========================

def choose_price_from(items: list[ServicePricingItem]) -> tuple[float | None, str | None, str | None]:
    prices = [
        item.price_rub
        for item in items
        if item.price_rub is not None and item.price_rub > 0
    ]

    if not prices:
        return None, None, None

    min_price = min(prices)

    selected = next(item for item in items if item.price_rub == min_price)

    return selected.price_rub, selected.price_unit, "pay-as-you-go"


def build_services_from_pricing_items(items: list[ServicePricingItem], provider: Provider) -> list[Service]:
    grouped: dict[str, list[ServicePricingItem]] = {}

    for item in items:
        grouped.setdefault(item.service_id, []).append(item)

    services = []

    for service_id, service_items in sorted(grouped.items()):
        profile = SERVICE_PROFILES.get(service_id, SERVICE_PROFILES["t1-cloud-other"])
        price_from, price_unit, pricing_model = choose_price_from(service_items)

        compliance_tags = ["152-FZ"] if provider.is_152fz_compliant else []

        services.append(
            Service(
                service_id=service_id,
                provider_id=provider.provider_id,
                name=profile["name"],
                category=profile["category"],
                description=profile["description"],
                tech_stack_tags=unique_list(profile["tech_stack_tags"]),
                use_case_tags=unique_list(profile["use_case_tags"]),
                compliance_tags=compliance_tags,
                regions=provider.regions,
                pricing_model=pricing_model,
                price_from_rub=price_from,
                price_unit=price_unit,
                support_level=None,
                service_url=profile.get("service_url"),
                source_url=provider.pricing_url or provider.source_url,
                parsed_at=now_utc(),
                is_synthetic=False,
            )
        )

    return services
