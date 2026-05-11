import re

from algorithm.cloudmatch.core.constants import REQUIRED_COMPLIANCE_TAG
from algorithm.cloudmatch.data.catalog import get_available_regions
from algorithm.cloudmatch.geo.region_resolver import (
    canonicalize_region,
    extract_region_from_text,
    match_available_region,
    resolve_nearby_available_regions,
)
from algorithm.cloudmatch.schemas.query import RequiredComponent, StructuredQuery


def normalize_string(value: str) -> str:
    return value.strip().lower()


def normalize_list(values: list[str]) -> list[str]:
    """
    Нормализует список строк.

    Важно:
    мы не проверяем tech_stack/use_case по жёсткому справочнику.
    Если пользователь указал новую технологию, она сохраняется.
    """

    normalized = []

    for value in values:
        item = normalize_string(value)

        if item and item not in normalized:
            normalized.append(item)

    return normalized


def normalize_region(region: str | None) -> str | None:
    """
    Нормализует пользовательский регион.

    Если регион уже есть в данных, возвращаем точное написание из catalog.
    Если региона нет в данных, сохраняем его в каноническом виде: pipeline
    подберет ближайший доступный регион отдельно.
    """

    if region is None:
        return None

    available_regions = get_available_regions()
    canonical_region = canonicalize_region(region)

    matched_region = match_available_region(
        requested_region=canonical_region,
        available_regions=available_regions,
    )

    return matched_region or canonical_region


def normalize_required_components(
    components: list[RequiredComponent],
) -> list[RequiredComponent]:
    """
    Нормализует required_components.

    Важно:
    если появился новый component, которого нет в нашем кодовом списке,
    мы его не выкидываем. Он сохранится и пойдёт в retrieval query.
    """

    normalized_components = []
    seen = set()

    for component in components:
        component_name = normalize_string(component.component)

        if not component_name or component_name in seen:
            continue

        seen.add(component_name)

        normalized_components.append(
            RequiredComponent(
                component=component_name,
                required=component.required,
                subtype=normalize_string(component.subtype) if component.subtype else None,
                db_engine=normalize_string(component.db_engine) if component.db_engine else None,
                reason=component.reason,
            )
        )

    return normalized_components


def add_unique(values: list[str], new_value: str) -> None:
    if new_value not in values:
        values.append(new_value)


def has_component(query: StructuredQuery, component_name: str) -> bool:
    return any(
        component.component == component_name
        for component in query.required_components
    )


def add_component_if_missing(
    query: StructuredQuery,
    component_name: str,
    reason: str,
    db_engine: str | None = None,
    subtype: str | None = None,
) -> None:
    if has_component(query, component_name):
        return

    query.required_components.append(
        RequiredComponent(
            component=component_name,
            required=True,
            subtype=subtype,
            db_engine=db_engine,
            reason=reason,
        )
    )


def infer_use_case_and_components(query: StructuredQuery) -> None:
    """
    Достраивает очевидные use_case и required_components.

    Это не ограничивает пользователя.
    Это только добавляет логически понятные компоненты,
    если LLM их пропустила.
    """

    tech_stack = set(query.tech_stack)

    if {"django", "fastapi", "flask", "python"}.intersection(tech_stack):
        add_unique(query.use_case, "backend")
        add_unique(query.use_case, "web-hosting")

        add_component_if_missing(
            query=query,
            component_name="compute",
            reason="Для backend/web-приложения нужна среда выполнения.",
        )

    if "postgresql" in tech_stack:
        add_unique(query.use_case, "database")

        add_component_if_missing(
            query=query,
            component_name="managed_database",
            db_engine="postgresql",
            reason="В запросе указана PostgreSQL-база данных.",
        )

    if "mysql" in tech_stack:
        add_unique(query.use_case, "database")

        add_component_if_missing(
            query=query,
            component_name="managed_database",
            db_engine="mysql",
            reason="В запросе указана MySQL-база данных.",
        )

    if "redis" in tech_stack:
        add_unique(query.use_case, "database")

        add_component_if_missing(
            query=query,
            component_name="managed_database",
            db_engine="redis",
            reason="В запросе указан Redis.",
        )

    if "clickhouse" in tech_stack:
        add_unique(query.use_case, "database")
        add_unique(query.use_case, "analytics")

        add_component_if_missing(
            query=query,
            component_name="managed_database",
            db_engine="clickhouse",
            reason="В запросе указан ClickHouse.",
        )

    if "s3" in tech_stack:
        add_unique(query.use_case, "object-storage")

        add_component_if_missing(
            query=query,
            component_name="object_storage",
            subtype="s3",
            reason="В запросе указан S3/object storage.",
        )

    if "docker" in tech_stack:
        add_unique(query.use_case, "devops")

    if "kubernetes" in tech_stack:
        add_unique(query.use_case, "devops")

        add_component_if_missing(
            query=query,
            component_name="kubernetes",
            reason="В запросе указан Kubernetes.",
        )

    raw_query = normalize_string(query.raw_query).replace("ё", "е")

    if any(
        marker in raw_query
        for marker in [
            "сервер",
            "виртуальная машина",
            "виртуальную машину",
            "vps",
            "vm",
            "compute",
        ]
    ):
        add_unique(query.use_case, "compute")
        add_component_if_missing(
            query=query,
            component_name="compute",
            reason="В запросе нужен сервер или виртуальная машина.",
        )

    if any(
        marker in raw_query
        for marker in [
            "база данных",
            "базу данных",
            "базы данных",
            "бд",
            "субд",
            "database",
            "databases",
        ]
    ):
        add_unique(query.use_case, "database")

        add_component_if_missing(
            query=query,
            component_name="managed_database",
            reason="В запросе указана база данных.",
        )

    if any(
        marker in raw_query
        for marker in [
            "хранение изображ",
            "изображения товаров",
            "картинки товаров",
            "медиа",
            "файлы",
            "s3",
            "object storage",
            "объектное хранилище",
        ]
    ):
        add_unique(query.use_case, "object-storage")
        add_component_if_missing(
            query=query,
            component_name="object_storage",
            subtype="s3",
            reason="В запросе нужно хранение файлов или изображений.",
        )

    if any(
        marker in raw_query
        for marker in [
            "резервное копирование",
            "резервного копирования",
            "бэкап",
            "backup",
            "backup storage",
        ]
    ):
        add_unique(query.use_case, "backup")
        add_component_if_missing(
            query=query,
            component_name="backup",
            reason="В запросе нужно резервное копирование.",
        )

    if any(
        marker in raw_query
        for marker in [
            "масштаб",
            "росте нагрузки",
            "распределение нагрузки",
            "load balancer",
            "балансиров",
        ]
    ):
        add_unique(query.use_case, "scaling")
        add_component_if_missing(
            query=query,
            component_name="load_balancer",
            reason="Для масштабирования и распределения нагрузки может понадобиться балансировщик.",
        )


def infer_task_category_and_intent(query: StructuredQuery) -> None:
    components = {
        component.component
        for component in query.required_components
    }

    use_cases = set(query.use_case)

    if query.task_category is None:
        if "web-hosting" in use_cases or "backend" in use_cases:
            query.task_category = "web-hosting"
        elif "database" in use_cases or "managed_database" in components:
            query.task_category = "database"
        elif "object-storage" in use_cases or "object_storage" in components:
            query.task_category = "storage"
        elif "backup" in use_cases or "backup" in components:
            query.task_category = "backup"
        elif "compute" in use_cases or "compute" in components:
            query.task_category = "compute"
        elif "analytics" in use_cases or "analytics" in components:
            query.task_category = "analytics"
        elif "ml" in use_cases or "ai_ml" in components:
            query.task_category = "ml"
        elif "devops" in use_cases or "kubernetes" in components:
            query.task_category = "devops"

    if query.intent is None:
        if query.task_category == "web-hosting":
            query.intent = "deploy_application"
        elif query.task_category == "database":
            query.intent = "setup_database"
        elif query.task_category == "storage":
            query.intent = "store_files"
        elif query.task_category == "backup":
            query.intent = "backup_data"
        elif query.task_category == "compute":
            query.intent = "setup_infrastructure"
        elif query.task_category == "analytics":
            query.intent = "analyze_data"
        elif query.task_category == "ml":
            query.intent = "run_ml"
        elif query.task_category == "devops":
            query.intent = "setup_infrastructure"


def normalize_constraints(query: StructuredQuery) -> None:
    """
    Нормализует ограничения.

    Строго проверяем только region, потому что он используется как hard filter.
    """

    query.constraints.compliance_required = True
    query.constraints.compliance_tags = [REQUIRED_COMPLIANCE_TAG]

    raw_region = query.constraints.region or extract_region_from_text(
        query.raw_query
    )

    if raw_region:
        available_regions = get_available_regions()
        normalized_region = normalize_region(raw_region)
        exact_region = match_available_region(
            requested_region=normalized_region,
            available_regions=available_regions,
        )
        region_candidates = resolve_nearby_available_regions(
            requested_region=normalized_region,
            available_regions=available_regions,
        )

        query.constraints.region = normalized_region
        query.constraints.region_required = True
        query.constraints.effective_region = exact_region or (
            region_candidates[0] if region_candidates else None
        )
        query.constraints.nearby_regions = [
            region
            for region in region_candidates
            if region not in {exact_region, query.constraints.effective_region}
        ]
        query.constraints.region_fallback_used = (
            exact_region is None
            and query.constraints.effective_region is not None
        )
        query.constraints.region_fallback_reason = (
            _build_region_fallback_reason(
                requested_region=normalized_region,
                effective_region=query.constraints.effective_region,
            )
            if query.constraints.region_fallback_used
            else None
        )
    else:
        query.constraints.region = None
        query.constraints.region_required = False
        query.constraints.effective_region = None
        query.constraints.nearby_regions = []
        query.constraints.region_fallback_used = False
        query.constraints.region_fallback_reason = None

    extracted_budget_max = extract_budget_max_from_text(query.raw_query)
    if extracted_budget_max is not None:
        query.constraints.budget_max = extracted_budget_max

    if query.constraints.budget_max is not None or query.constraints.budget_min is not None:
        query.constraints.budget_required = True


def extract_budget_max_from_text(text: str) -> float | None:
    normalized = " ".join(text.strip().lower().replace("ё", "е").split())

    if any(
        marker in normalized
        for marker in (
            "без бюджета",
            "любой бюджет",
            "бюджет любой",
            "бюджет не важен",
            "бюджет неважен",
            "по бюджету все равно",
            "по бюджету всё равно",
        )
    ):
        return None

    if re.search(r"(?:за|на|бюджет)\s+один\s+руб", normalized):
            return 1.0

    patterns = (
        r"(?:до|максимум|не больше|не дороже)\s+(\d[\d\s]*(?:[.,]\d+)?)\s*(тысяч|тыс|к|k)?",
        r"(\d[\d\s]*(?:[.,]\d+)?)\s*(тысяч|тыс|к|k)\s*(?:руб|рублей|р)?",
        r"(\d[\d\s]{3,})\s*(?:руб|рублей|р)?",
    )

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue

        amount = float(match.group(1).replace(" ", "").replace(",", "."))
        multiplier = 1000 if len(match.groups()) > 1 and match.group(2) else 1
        return amount * multiplier

    return None


def _build_region_fallback_reason(
    requested_region: str | None,
    effective_region: str | None,
) -> str | None:
    if requested_region is None or effective_region is None:
        return None

    return (
        f"В данных нет прямого региона {requested_region}; "
        f"для поиска выбран ближайший доступный регион {effective_region}."
    )


def infer_confidence(query: StructuredQuery) -> None:
    if query.confidence < 0:
        query.confidence = 0.0

    if query.confidence > 1:
        query.confidence = 1.0

    if query.confidence > 0:
        return

    score = 0.0

    if query.tech_stack:
        score += 0.25

    if query.use_case:
        score += 0.25

    if query.required_components:
        score += 0.25

    if query.constraints.region:
        score += 0.10

    if query.constraints.budget_max is not None or query.constraints.budget_min is not None:
        score += 0.10

    if score == 0:
        query.confidence = 0.0
    else:
        query.confidence = min(score, 0.95)


def validate_structured_query(query: StructuredQuery) -> StructuredQuery:
    """
    Главная функция валидации.

    Принцип:
    - tech_stack/use_case/requirements не ограничиваем жёсткими списками;
    - новые значения сохраняем;
    - регион сохраняем из запроса, а для hard filter выбираем effective_region;
    - 152-ФЗ всегда добавляем как обязательное условие.
    """

    query.tech_stack = normalize_list(query.tech_stack)
    query.use_case = normalize_list(query.use_case)

    query.required_components = normalize_required_components(
        query.required_components
    )

    infer_use_case_and_components(query)
    infer_task_category_and_intent(query)
    normalize_constraints(query)
    infer_confidence(query)

    return query
