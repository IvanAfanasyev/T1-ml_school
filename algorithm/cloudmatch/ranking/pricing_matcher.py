from algorithm.cloudmatch.geo.region_resolver import canonicalize_region, normalize_location_key
from algorithm.cloudmatch.schemas.pricing import ServicePricingItem
from algorithm.cloudmatch.schemas.query import StructuredQuery
from algorithm.cloudmatch.schemas.service import Service


MAX_DISPLAY_PRICE_RUB = 1_000_000


def normalize(value: object) -> str:
    if value is None:
        return ""

    return str(value).strip().lower()


def normalize_region(value: object) -> str:
    if value is None:
        return ""

    region = str(value)
    return normalize_location_key(canonicalize_region(region) or region)


def canonical(value: object) -> str:
    return normalize(value).replace("_", "-").replace(" ", "-")


def build_item_text(item: ServicePricingItem) -> str:
    parts = [
        item.pricing_item_id,
        item.item_name,
        item.item_type,
        item.price_unit or "",
        item.billing_period or "",
        item.region or "",
        " ".join(item.configuration_tags),
        item.raw_text or "",
    ]

    return " ".join(part for part in parts if part).lower()


def build_service_text(service: Service) -> str:
    parts = [
        service.service_id,
        service.provider_id,
        service.name,
        service.category,
        service.description,
        " ".join(service.tech_stack_tags),
        " ".join(service.use_case_tags),
        " ".join(service.compliance_tags),
        " ".join(service.regions),
        service.pricing_model or "",
        service.price_unit or "",
        service.support_level or "",
    ]

    return " ".join(part for part in parts if part).lower()


def is_positive_price(item: ServicePricingItem) -> bool:
    return item.price_rub is not None and item.price_rub > 0


def is_suspicious_display_price(item: ServicePricingItem) -> bool:
    """
    Отсекает явно странные цены для пользовательского вывода.

    Это не значит, что строка точно неправильная.
    Это значит, что её нельзя безопасно показывать пользователю
    как понятный тариф без дополнительной проверки.
    """

    if item.price_rub is None:
        return True

    if item.price_rub <= 0:
        return True

    if item.price_rub > MAX_DISPLAY_PRICE_RUB:
        return True

    return False


def is_backup_item(item: ServicePricingItem) -> bool:
    text = build_item_text(item)
    item_type = canonical(item.item_type)

    return (
        "backup" in item_type
        or "backup" in text
        or "резерв" in text
        or "бэкап" in text
        or "копирован" in text
    )


def is_storage_item(item: ServicePricingItem) -> bool:
    text = build_item_text(item)
    item_type = canonical(item.item_type)
    price_unit = normalize(item.price_unit)

    return (
        "storage" in item_type
        or "disk" in item_type
        or "гб" in price_unit
        or "gb" in price_unit
        or "хранилищ" in text
        or "диск" in text
        or "storage" in text
    )


def is_compute_resource_item(item: ServicePricingItem) -> bool:
    text = build_item_text(item)
    item_type = canonical(item.item_type)

    return (
        item_type in {"ram", "cpu", "vcpu", "disk", "gpu"}
        or "ram" in text
        or "vcpu" in text
        or "cpu" in text
        or "gpu" in text
        or "диск" in text
        or "оператив" in text
    )


def get_database_component_type(item: ServicePricingItem) -> str | None:
    text = build_item_text(item)
    item_type = canonical(item.item_type)

    if item_type in {"cpu", "vcpu"} or "vcpu" in text or "cpu" in text:
        return "cpu"

    if item_type == "ram" or "ram" in text or "память" in text:
        return "ram"

    if item_type in {"storage", "disk"} or "диск" in text or "storage" in text:
        return "storage"

    return None


def select_database_component_items(
    pricing_items: list[ServicePricingItem],
    limit: int = 3,
) -> list[ServicePricingItem]:
    best_by_component: dict[str, ServicePricingItem] = {}
    component_order = ("cpu", "ram", "storage")

    for item in pricing_items:
        if is_suspicious_display_price(item) or is_backup_item(item):
            continue

        component_type = get_database_component_type(item)

        if component_type not in component_order:
            continue

        current = best_by_component.get(component_type)
        if current is None or (item.price_rub or float("inf")) < (
            current.price_rub or float("inf")
        ):
            best_by_component[component_type] = item

    return [
        best_by_component[component_type]
        for component_type in component_order
        if component_type in best_by_component
    ][:limit]


def is_kubernetes_service(service: Service) -> bool:
    service_text = build_service_text(service)
    category = canonical(service.category)
    tags = {
        canonical(tag)
        for tag in [
            *service.tech_stack_tags,
            *service.use_case_tags,
        ]
    }

    return (
        category in {"kubernetes", "managed-kubernetes", "containers", "containers-and-serverless"}
        or "kubernetes" in service_text
        or "kubernetes" in tags
    )


def is_compute_service(service: Service) -> bool:
    service_text = build_service_text(service)
    category = canonical(service.category)
    tags = {
        canonical(tag)
        for tag in [
            *service.tech_stack_tags,
            *service.use_case_tags,
        ]
    }

    return (
        category
        in {
            "compute",
            "cloud-compute",
            "virtual-machines",
            "virtual-servers",
            "dedicated-servers",
            "iaas",
            "servers",
            "containers-and-serverless",
        }
        or "compute" in tags
        or "virtual-machine" in tags
        or "виртуаль" in service_text
    )


def is_other_item(item: ServicePricingItem) -> bool:
    return canonical(item.item_type) in {"other", "unknown", ""}


def is_database_main_item(item: ServicePricingItem, service: Service) -> bool:
    """
    Проверяет, похожа ли тарифная строка на основную цену database-сервиса.

    Для Managed PostgreSQL не считаем основной ценой:
    - backup;
    - storage;
    - ram;
    - disk;
    - cpu;
    - other.
    """

    if not is_positive_price(item):
        return False

    if is_backup_item(item):
        return False

    if is_storage_item(item):
        return False

    if is_compute_resource_item(item):
        return False

    if is_other_item(item):
        return False

    text = build_item_text(item)
    item_type = canonical(item.item_type)

    allowed_item_types = {
        "database",
        "db",
        "instance",
        "cluster",
        "database-instance",
        "db-instance",
    }

    if item_type in allowed_item_types:
        return True

    database_markers = [
        "postgresql",
        "postgres",
        "mysql",
        "clickhouse",
        "redis",
        "opensearch",
        "kafka",
        "database",
        "db",
        "cluster",
        "instance",
        "субд",
        "база данных",
        "кластер",
        "инстанс",
    ]

    service_text = build_service_text(service)

    # Должна быть связь с технологией сервиса.
    has_service_tech = any(
        normalize(tag) and normalize(tag) in text
        for tag in service.tech_stack_tags
    )

    has_database_marker = any(marker in text for marker in database_markers)

    return has_service_tech and has_database_marker or (
        "managed postgresql" in service_text and "postgresql" in text
    )


def is_kubernetes_main_item(item: ServicePricingItem) -> bool:
    if not is_positive_price(item):
        return False

    if is_storage_item(item):
        return False

    text = build_item_text(item)
    item_type = canonical(item.item_type)

    if any(
        marker in text
        for marker in [
            "балансировщик",
            "load balancer",
            "load-balancer",
            "public ip",
            "публичного ip",
            "repository",
            "registry",
            "репозитор",
        ]
    ):
        return False

    if item_type not in {"container", "service", "cluster", "kubernetes"}:
        return False

    return any(
        marker in text
        for marker in [
            "kubernetes",
            "master",
            "мастер",
            "cluster",
            "кластер",
            "node",
            "нода",
            "cce",
        ]
    )


def is_compute_main_item(item: ServicePricingItem) -> bool:
    if not is_positive_price(item):
        return False

    if is_storage_item(item):
        return False

    if is_backup_item(item):
        return False

    text = build_item_text(item)
    item_type = canonical(item.item_type)

    if any(
        marker in text
        for marker in [
            "балансировщик",
            "load balancer",
            "public ip",
            "публичн",
            "подсеть",
            "dns",
            "лиценз",
            "доступ к установке",
            "образ",
            "превышение лимита",
            "резервное копирование",
            "backup",
        ]
    ):
        return False

    if item_type in {"cpu-ram-vm", "cpu_ram_vm", "vm", "server", "instance"}:
        return True

    if item_type == "compute":
        return any(
            marker in text
            for marker in [
                "vcpu",
                "cpu",
                "процессор",
                "ядр",
                "gpu",
                "графическая карта",
                "server",
                "virtual machine",
                "виртуаль",
                "сервер",
            ]
        )

    if item_type == "cpu":
        return True

    return any(
        marker in text
        for marker in [
            "vcpu",
            "cpu",
            "ecs",
            "server",
            "virtual machine",
            "виртуаль",
            "сервер",
        ]
    )


def is_main_pricing_item_for_service(
    item: ServicePricingItem,
    service: Service,
) -> bool:
    """
    Определяет, можно ли использовать тарифную позицию
    как базовую цену услуги.

    Это используется для price_summary и budget_score.
    """

    if not is_positive_price(item):
        return False

    category = canonical(service.category)
    text = build_item_text(item)

    if is_kubernetes_service(service):
        return is_kubernetes_main_item(item)

    if category in {"database", "managed-database", "databases"}:
        return is_database_main_item(item, service)

    if is_compute_service(service):
        return is_compute_main_item(item)

    if category in {"backup", "cloud-backup"}:
        return is_backup_item(item)

    if category in {"storage", "object-storage", "cloud-storage"}:
        return is_storage_item(item) or "s3" in text

    if category == "cdn":
        return "cdn" in text or "traffic" in text or "трафик" in text

    if category in {"devops", "kubernetes", "containers", "containers-and-serverless"}:
        return is_kubernetes_main_item(item)

    if category in {"ai-ml", "ai/ml", "ml", "machine-learning"}:
        return (
            "gpu" in text
            or "jupyter" in text
            or "notebook" in text
            or "ml" in text
        )

    for tag in service.tech_stack_tags:
        tag_norm = normalize(tag)

        if tag_norm and tag_norm in text:
            return True

    return False


def is_item_allowed_for_display(
    item: ServicePricingItem,
    service: Service,
    query: StructuredQuery,
) -> bool:
    """
    Проверяет, можно ли показывать тарифную позицию пользователю.

    Для database-запросов показываем только основные database items.
    Не показываем backup/storage/ram/disk/other как тарифы PostgreSQL.
    """

    if is_suspicious_display_price(item):
        return False

    category = canonical(service.category)

    if category in {"database", "managed-database", "databases"}:
        return is_database_main_item(item, service) or get_database_component_type(item) is not None

    if is_kubernetes_service(service):
        return is_kubernetes_main_item(item)

    if is_compute_service(service):
        return is_compute_main_item(item)

    return is_main_pricing_item_for_service(
        item=item,
        service=service,
    )


def calculate_pricing_item_relevance(
    item: ServicePricingItem,
    service: Service,
    query: StructuredQuery,
) -> float:
    """
    Считает релевантность тарифной позиции для показа.

    Не влияет напрямую на ranking сервиса.
    Влияет только на то, какие тарифы увидит пользователь.
    """

    if not is_item_allowed_for_display(
        item=item,
        service=service,
        query=query,
    ):
        return 0.0

    text = build_item_text(item)
    item_type = canonical(item.item_type)

    score = 1.0

    for tech in query.tech_stack:
        tech_norm = normalize(tech)

        if tech_norm and tech_norm in text:
            score += 2.5

    for use_case in query.use_case:
        use_case_key = canonical(use_case)

        if use_case_key in text:
            score += 1.0

    for component in query.required_components:
        component_key = canonical(component.component)

        if component_key == "managed-database":
            if item_type in {"database", "db", "instance", "cluster"}:
                score += 2.5

            if any(
                marker in text
                for marker in [
                    "postgresql",
                    "mysql",
                    "clickhouse",
                    "redis",
                    "database",
                    "субд",
                ]
            ):
                score += 1.5

        if component_key == "object-storage":
            if is_storage_item(item) or "s3" in text:
                score += 2.0

        if component_key == "backup":
            if is_backup_item(item):
                score += 2.0

        if component_key == "compute":
            if any(marker in text for marker in ["vcpu", "cpu", "ram", "vm", "server", "сервер"]):
                score += 2.0

        if component_key == "kubernetes":
            if any(marker in text for marker in ["kubernetes", "master", "node", "cluster"]):
                score += 2.0

        if component_key == "load-balancer":
            if any(marker in text for marker in ["load balancer", "load-balancer", "балансиров"]):
                score += 2.0

    requested_region = query.constraints.effective_region or query.constraints.region

    if requested_region:
        required_region = normalize_region(requested_region)

        if normalize_region(item.region) == required_region:
            score += 0.5

    return score


def select_pricing_items_for_display(
    pricing_items: list[ServicePricingItem],
    service: Service,
    query: StructuredQuery,
    limit: int = 3,
) -> list[ServicePricingItem]:
    """
    Выбирает тарифные позиции для пользовательского вывода.

    Если у database-сервиса нет единой цены кластера, показываем базовые
    составляющие тарифа: CPU, RAM и диск.
    """

    category = canonical(service.category)

    if category in {"database", "managed-database", "databases"}:
        database_items = select_database_component_items(
            pricing_items=pricing_items,
            limit=limit,
        )

        if database_items:
            return database_items

    scored_items = []

    for item in pricing_items:
        score = calculate_pricing_item_relevance(
            item=item,
            service=service,
            query=query,
        )

        if score <= 0:
            continue

        scored_items.append((score, item))

    scored_items.sort(
        key=lambda pair: (
            pair[0],
            -(pair[1].price_rub or 0),
        ),
        reverse=True,
    )

    return [
        item
        for score, item in scored_items[:limit]
    ]
