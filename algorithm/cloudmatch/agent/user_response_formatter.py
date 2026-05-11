from algorithm.cloudmatch.data.repositories import DataRepository
from algorithm.cloudmatch.schemas.ranking import RankingResult, SearchResponse


def format_user_response(response: SearchResponse, data_repository: DataRepository) -> str:
    """Формирует пользовательский ответ без debug-полей."""
    lines: list[str] = []
    is_bundle = _is_bundle_response(response)

    lines.append("## Рекомендации")
    lines.append("")
    lines.append("**Как я понял задачу**")
    lines.extend(_format_structured_query(response))
    lines.append("")

    if is_bundle:
        lines.append("**Нужная связка сервисов**")
        lines.extend(_format_solution_components(response))
        lines.append("")

    lines.append("**Короткий вывод**")
    lines.append(response.summary or _build_default_summary(response))
    lines.append("")
    if is_bundle:
        lines.append("**Подобранные связки сервисов**")
        lines.extend(_format_bundle_rank_groups(response, data_repository))
    else:
        lines.append("**Top-3 сервиса**")
        for result in response.results:
            lines.extend(_format_service_card(result, data_repository))

    return "\n".join(lines)


def _is_bundle_response(response: SearchResponse) -> bool:
    return any(result.solution_component for result in response.results)


def _format_structured_query(response: SearchResponse) -> list[str]:
    query = response.structured_query
    constraints = query.get("constraints", {})
    lines = []

    if query.get("tech_stack"):
        lines.append(f"- Технологии: {', '.join(query['tech_stack'])}")
    if query.get("use_case"):
        lines.append(f"- Сценарии: {', '.join(query['use_case'])}")
    if constraints.get("region"):
        region = constraints.get("region")
        effective_region = constraints.get("effective_region")

        if constraints.get("region_fallback_used") and effective_region:
            lines.append(
                f"- Регион: {region}; ближайший доступный: {effective_region}"
            )
        else:
            lines.append(f"- Регион: {region}")
    if constraints.get("budget_max"):
        lines.append(f"- Бюджет: до {_format_number(constraints.get('budget_max'))} руб. в месяц")

    requirements = query.get("requirements") or []
    if requirements:
        req_parts = [f"{item.get('name')}={item.get('value')}" for item in requirements]
        lines.append(f"- Дополнительные требования: {', '.join(req_parts)}")

    return lines or ["- Ключевые параметры не были явно выделены."]


def _format_solution_components(response: SearchResponse) -> list[str]:
    components = response.structured_query.get("required_components") or []

    if not components:
        return []

    return [
        f"{index}. {_component_label(item)}"
        for index, item in enumerate(components, start=1)
    ]


def _format_bundle_rank_groups(
    response: SearchResponse,
    data_repository: DataRepository,
) -> list[str]:
    grouped: dict[int, list[RankingResult]] = {}

    for result in response.results:
        component_rank = result.solution_component_rank or result.rank
        grouped.setdefault(component_rank, []).append(result)

    lines: list[str] = []

    for component_rank in sorted(grouped):
        lines.append("")
        bundle_results = grouped[component_rank]
        lines.append(f"### #{component_rank}")
        lines.append(_format_bundle_title(bundle_results, data_repository))
        lines.append("")
        lines.append(_build_bundle_explanation(component_rank, bundle_results))

        for result in bundle_results:
            lines.extend(_format_service_card(result, data_repository))

    return lines


def _format_bundle_title(
    results: list[RankingResult],
    data_repository: DataRepository,
) -> str:
    parts = []

    for result in results:
        provider = data_repository.providers_by_id.get(result.service.provider_id)
        provider_name = provider.name if provider else result.service.provider_id
        parts.append(f"{provider_name} — {result.service.name}")

    return " + ".join(parts)


def _build_bundle_explanation(rank: int, results: list[RankingResult]) -> str:
    roles = ", ".join(
        _component_title(result.solution_component or "")
        for result in results
        if result.solution_component
    )
    intro = (
        "Эта связка собрана из сервисов одного провайдера, чтобы компоненты проще было внедрять и сопровождать вместе."
        if rank == 1
        else "Это альтернативная связка от одного провайдера для тех же частей задачи."
    )
    return f"{intro} Она закрывает роли: {roles}."


def _component_label(component: dict) -> str:
    name = component.get("component")
    db_engine = component.get("db_engine")
    subtype = component.get("subtype")
    reason = component.get("reason")
    labels = {
        "compute": "Compute / Virtual Machine / App runtime",
        "managed_database": "Managed database",
        "object_storage": "Object Storage / S3",
        "backup": "Backup",
        "kubernetes": "Managed Kubernetes",
        "load_balancer": "Load Balancer",
        "analytics": "Analytics",
        "ai_ml": "AI / ML",
    }
    title = labels.get(name, str(name).replace("_", " ").title())

    if db_engine:
        title = f"{title} ({db_engine})"
    elif subtype:
        title = f"{title} ({subtype})"

    return f"{title} — {reason}" if reason else title


def _format_service_card(result: RankingResult, data_repository: DataRepository) -> list[str]:
    service = result.service
    provider = data_repository.providers_by_id.get(service.provider_id)
    provider_name = provider.name if provider else service.provider_id
    service_url = _get_service_url(service)

    title = f"### {result.rank}. {provider_name} — {service.name}"
    if result.solution_component:
        title += f" ({_component_title(result.solution_component)})"

    lines = ["", title]
    if result.solution_component_reason:
        lines.append(f"- Роль в связке: {result.solution_component_reason}")

    lines.append(f"- Категория: {service.category}")
    if service_url:
        lines.append(f"- Ссылка: {service_url}")
    lines.append(f"- Цена: {_format_price(result)}")

    matched_line = _format_matched_line(result)
    if matched_line:
        lines.append(f"- Что совпало: {matched_line}")

    missing_line = _format_missing_line(result)
    if missing_line:
        lines.append(f"- Что не подтверждено в данных: {missing_line}")

    lines.append("")
    lines.append("Почему на этом месте:")
    lines.append(result.explanation or _build_rank_explanation(result))

    lines.append("")
    lines.append("Тарифы:")
    if not result.selected_pricing_items:
        lines.append("- Точные релевантные тарифные позиции для этого запроса не найдены.")
        lines.append("- Проверьте актуальную цену по ссылке на сервис.")
    else:
        for item in result.selected_pricing_items:
            lines.append(f"- {item.item_name}: {_format_pricing_item_price(item)}; период: {item.billing_period or 'не указан'}")
    return lines


def _component_title(component: str) -> str:
    labels = {
        "compute": "backend/runtime",
        "managed_database": "база данных",
        "object_storage": "хранение файлов",
        "backup": "резервное копирование",
        "kubernetes": "контейнеры",
        "load_balancer": "масштабирование",
    }
    return labels.get(component, component.replace("_", " "))


def _build_default_summary(response: SearchResponse) -> str:
    if _is_bundle_response(response):
        return (
            "Запрос состоит из нескольких инфраструктурных частей, поэтому система "
            "подобрала не один универсальный сервис, а набор сервисов под разные роли."
        )

    return "Система построила top-3 рекомендаций."


def _get_service_url(service) -> str | None:
    return getattr(service, "service_url", None) or getattr(service, "source_url", None)


def _format_price(result: RankingResult) -> str:
    price = result.price_summary.price_from_rub
    unit = result.price_summary.price_unit
    if price is None:
        return "точная стартовая цена не определена в нормализованных данных"
    return f"от {_format_number(price)} {unit}" if unit else f"от {_format_number(price)} руб."


def _format_pricing_item_price(item) -> str:
    if item.price_rub is None:
        return "цена не определена"
    return f"{_format_number(item.price_rub)} {item.price_unit}" if item.price_unit else f"{_format_number(item.price_rub)} руб."


def _format_number(value) -> str:
    number = float(value)

    if number.is_integer():
        return f"{int(number):,}".replace(",", " ")

    return f"{number:,.6f}".rstrip("0").rstrip(".").replace(",", " ")


def _format_matched_line(result: RankingResult) -> str:
    matched = result.matched_entities
    parts = []
    if matched.matched_tech_stack:
        parts.append(_format_entity_values(matched.matched_tech_stack))
    if matched.matched_use_case:
        parts.append(_format_entity_values(matched.matched_use_case))
    if matched.matched_components:
        parts.append(_format_entity_values(matched.matched_components))
    if matched.matched_requirements:
        parts.append(_format_entity_values(matched.matched_requirements))
    if matched.matched_region:
        parts.append(f"регион {matched.matched_region}")
    if matched.budget_status == "within_budget":
        parts.append("укладывается в бюджет")
    return "; ".join(parts)


def _format_missing_line(result: RankingResult) -> str:
    matched = result.matched_entities
    parts = []
    if matched.missing_tech_stack:
        parts.append(_format_entity_values(matched.missing_tech_stack))
    if matched.missing_use_case:
        parts.append(_format_entity_values(matched.missing_use_case))
    if matched.missing_components:
        parts.append(_format_entity_values(matched.missing_components))
    if matched.missing_requirements:
        parts.append(_format_entity_values(matched.missing_requirements))
    if matched.budget_status == "price_unknown":
        parts.append("цена не определена")
    if matched.budget_status == "over_budget":
        parts.append("выше бюджета")
    return "; ".join(parts)


def _format_entity_values(values: list[str]) -> str:
    return ", ".join(_humanize_entity_value(value) for value in values)


def _humanize_entity_value(value: str) -> str:
    text = str(value)
    normalized = text.lower()

    if normalized.startswith("scalability="):
        return "быстрое масштабирование"

    if normalized == "billing_period=month":
        return "помесячная тарификация"

    if normalized == "billing_period=hour":
        return "почасовая тарификация"

    if normalized.startswith("budget_max="):
        amount = text.split("=", 1)[1]
        return f"бюджет до {amount} руб."

    return text.replace("_", " ")


def _build_rank_explanation(result: RankingResult) -> str:
    service = result.service
    matched = result.matched_entities
    if result.solution_component:
        component_rank = result.solution_component_rank or result.rank
        parts = [
            f"{service.name} занял {component_rank}-е место в подзапросе "
            f"«{_component_title(result.solution_component)}», потому что лучше других "
            "кандидатов для этой роли совпал с запросом и структурированными требованиями."
        ]
    else:
        parts = [
            f"{service.name} занял {result.rank}-е место в общем рейтинге, "
            "потому что лучше других кандидатов сочетает поисковую близость и совпадение требований."
        ]
    if matched.matched_tech_stack:
        parts.append(f"Совпавшие технологии: {', '.join(matched.matched_tech_stack)}.")
    if matched.matched_use_case:
        parts.append(f"Совпавшие сценарии: {', '.join(matched.matched_use_case)}.")
    if matched.matched_components:
        parts.append(f"Закрытые компоненты: {', '.join(matched.matched_components)}.")
    if matched.missing_tech_stack or matched.missing_components or matched.missing_requirements:
        parts.append("Часть требований не подтверждена в нормализованных данных, поэтому сервис может требовать дополнительной проверки.")
    return " ".join(parts)
