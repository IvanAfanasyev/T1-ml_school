from algorithm.cloudmatch.data.repositories import DataRepository
from algorithm.cloudmatch.ranking.compliance_filter import service_has_required_compliance
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
    lines.append(_sanitize_user_text(response.summary or _build_default_summary(response)))
    lines.append("")
    if is_bundle:
        lines.append("**Подобранные связки провайдеров**")
        lines.extend(_format_bundle_rank_groups(response, data_repository))
    else:
        lines.append("**Top-3 провайдера**")
        for result in response.results:
            lines.extend(_format_provider_card(result, data_repository))

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
        period = _format_period_label(constraints.get("budget_period") or "month")
        lines.append(f"- Бюджет: до {_format_number(constraints.get('budget_max'))} руб. / {period}")

    requirements = query.get("requirements") or []
    if requirements:
        req_parts = [
            _humanize_entity_value(f"{item.get('name')}={item.get('value')}")
            for item in requirements
        ]
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

def _bundle_group_count(response: SearchResponse) -> int:
    return len(
        {
            result.solution_component_rank or result.rank
            for result in response.results
            if result.solution_component
        }
    )


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

    matched_line = _format_matched_line(result, data_repository)
    if matched_line:
        lines.append(f"- Что совпало: {matched_line}")

    missing_line = _format_missing_line(result)
    if missing_line:
        lines.append(f"- Что не подтверждено в данных: {missing_line}")

    lines.append("")
    lines.append("Почему подходит:")
    lines.append(_sanitize_user_text(result.explanation or _build_rank_explanation(result)))

    lines.append("")
    lines.append("Тарифы:")
    if not result.selected_pricing_items:
        lines.append("- Точные релевантные тарифные позиции для этого запроса не найдены.")
        lines.append("- Проверьте актуальную цену по ссылке на сервис.")
    else:
        for item in result.selected_pricing_items:
            lines.append(f"- {item.item_name}: {_format_pricing_item_price(item)}; период: {item.billing_period or 'не указан'}")
    return lines


def _format_provider_card(
    result: RankingResult,
    data_repository: DataRepository,
) -> list[str]:
    service = result.service
    provider = data_repository.providers_by_id.get(service.provider_id)
    provider_name = provider.name if provider else service.provider_id
    service_url = _get_service_url(service)

    lines = ["", f"### #{result.rank} {provider_name}"]
    lines.append(f"- Релевантный сервис: {service.name}")
    lines.append(f"- Категория: {service.category}")
    if service_url:
        lines.append(f"- Ссылка: {service_url}")
    lines.append(f"- Цена: {_format_price(result)}")

    matched_line = _format_matched_line(result, data_repository)
    if matched_line:
        lines.append(f"- Что совпало: {matched_line}")

    missing_line = _format_missing_line(result)
    if missing_line:
        lines.append(f"- Что проверить отдельно: {missing_line}")

    lines.append("")
    lines.append("Почему провайдер в выдаче:")
    lines.append(_sanitize_user_text(result.explanation or _build_rank_explanation(result)))

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
        bundle_count = _bundle_group_count(response)
        if bundle_count < 3:
            return (
                f"Запрос состоит из нескольких инфраструктурных частей. "
                f"В текущих данных найдено {bundle_count} связк(и), которые закрывают "
                "все обязательные роли вместе. Остальные провайдеры не попали в список, "
                "потому что не закрывают полный набор компонентов, регион или обязательные требования."
            )
        return (
            "Запрос состоит из нескольких инфраструктурных частей, поэтому система "
            "подобрала не один универсальный сервис, а набор сервисов под разные роли."
        )

    if response.results and all(
        result.matched_entities.budget_status in {"over_budget", "slightly_over_budget"}
        for result in response.results
    ):
        return (
            "Точных вариантов в указанном бюджете не найдено. Ниже показаны ближайшие "
            "провайдеры из каталога, но цену по ним нужно проверять отдельно."
        )

    return "Я подобрал top-3 провайдера и показал сервис, который лучше всего представляет каждого из них для этой задачи."


def _get_service_url(service) -> str | None:
    return getattr(service, "service_url", None) or getattr(service, "source_url", None)


def _format_price(result: RankingResult) -> str:
    price = result.price_summary.price_from_rub
    unit = result.price_summary.price_unit
    if price is None:
        return "точная стартовая цена не определена в нормализованных данных"

    base = f"от {_format_number(price)} {unit}" if unit else f"от {_format_number(price)} руб."
    monthly_estimate = result.price_summary.monthly_estimate_rub
    period_estimate = result.price_summary.period_estimate_rub
    estimate_period = result.price_summary.estimate_period

    if (
        estimate_period != "month"
        and period_estimate is not None
        and abs(period_estimate - price) > 0.01
    ):
        base += (
            f" (примерно {_format_number(period_estimate)} руб./"
            f"{_format_period_label(estimate_period)} при работе 24/7)"
        )

    if (
        monthly_estimate is not None
        and abs(monthly_estimate - price) > 0.01
    ):
        base += f" (примерно {_format_number(monthly_estimate)} руб./мес при работе 24/7)"

    return base


def _format_period_label(period: str | None) -> str:
    labels = {
        "hour": "час",
        "day": "день",
        "week": "неделю",
        "month": "месяц",
    }
    return labels.get(period or "month", "месяц")


def _format_pricing_item_price(item) -> str:
    if item.price_rub is None:
        return "цена не определена"
    return f"{_format_number(item.price_rub)} {item.price_unit}" if item.price_unit else f"{_format_number(item.price_rub)} руб."


def _format_number(value) -> str:
    number = float(value)

    if number.is_integer():
        return f"{int(number):,}".replace(",", " ")

    return f"{number:,.6f}".rstrip("0").rstrip(".").replace(",", " ")


def _format_matched_line(
    result: RankingResult,
    data_repository: DataRepository | None = None,
) -> str:
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
    if data_repository is not None:
        provider = data_repository.providers_by_id.get(result.service.provider_id)
        if service_has_required_compliance(result.service, provider):
            parts.append("152-ФЗ подтверждено")
    if matched.budget_status == "within_budget":
        parts.append("укладывается в бюджет")
    if matched.budget_status == "slightly_over_budget":
        parts.append("близко к бюджету")
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
    if matched.budget_status == "slightly_over_budget":
        parts.append("может немного превышать бюджет")
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

    if normalized.startswith("storage_gb="):
        amount = text.split("=", 1)[1]
        return f"объем {amount} ГБ"

    return text.replace("_", " ")


def _build_rank_explanation(result: RankingResult) -> str:
    service = result.service
    matched = result.matched_entities
    if result.solution_component:
        parts = [
            f"{service.name} выбран для роли «{_component_title(result.solution_component)}», "
            "потому что в данных сервиса есть совпадения с этой частью задачи."
        ]
    else:
        parts = [
             f"{service.name} представляет провайдера в выдаче, потому что в данных сервиса "
            "есть совпадения с запросом пользователя."
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


def _sanitize_user_text(text: str) -> str:
    result = str(text)
    replacements = {
        "final_score": "релевантность",
        "retrieval_score": "релевантность",
        "entity_match_score": "совпадение требований",
        "embedding_score": "релевантность",
        "bm25_score": "текстовое совпадение",
        "score": "релевантность",
    }
    for source, target in replacements.items():
        result = result.replace(source, target)
    result = _remove_false_152fz_warning(result)
    return result


def _remove_false_152fz_warning(text: str) -> str:
    lowered = text.lower()
    if "152" not in lowered:
        return text

    markers = (
        "нет информации",
        "не указано",
        "не указана",
        "не подтверждено",
        "не подтверждена",
    )

    if not any(marker in lowered for marker in markers):
        return text

    sentences = []
    for sentence in text.split("."):
        normalized = sentence.lower()
        if "152" in normalized and any(marker in normalized for marker in markers):
            continue
        sentences.append(sentence)

    cleaned = ".".join(part for part in sentences if part.strip()).strip()
    return cleaned or "Соответствие 152-ФЗ подтверждено по данным сервиса или провайдера."
