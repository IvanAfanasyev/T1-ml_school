import re
import uuid
from typing import Any

from pydantic import BaseModel, Field

from algorithm.cloudmatch.agent.query_extractor import QueryExtractor
from algorithm.cloudmatch.geo.region_resolver import canonicalize_region, extract_region_from_text
from algorithm.cloudmatch.schemas.query import StructuredQuery


ACTION_CLARIFICATION = "clarification"
ACTION_SEARCH = "search"
ACTION_OFF_TOPIC = "off_topic"

FIELD_TASK = "task"
FIELD_DATABASE_ENGINE = "database_engine"
FIELD_TECH_STACK = "tech_stack"
FIELD_REGION = "region"
FIELD_BUDGET = "budget"


class DialogSlots(BaseModel):
    request_type: str | None = None
    service_area: str | None = None
    technologies: list[str] = Field(default_factory=list)
    db_engine: str | None = None
    region: str | None = None
    budget_max: float | None = None
    budget_period: str | None = None


class DialogMemory(BaseModel):
    user_id: str
    chat_id: str
    slots: DialogSlots = Field(default_factory=DialogSlots)
    pending_fields: list[str] = Field(default_factory=list)
    ignored_fields: list[str] = Field(default_factory=list)
    last_search_query: str | None = None
    messages_count: int = 0


class DialogDecision(BaseModel):
    user_id: str
    chat_id: str
    action: str
    assistant_message: str
    clarification_questions: list[str] = Field(default_factory=list)
    search_query: str | None = None
    memory: DialogMemory


class DialogManager:
    def __init__(self, slot_extractor: "DialogSlotExtractor | None" = None) -> None:
        self.slot_extractor = slot_extractor or RuleBasedDialogSlotExtractor()

    def handle_message(
        self,
        user_id: str,
        chat_id: str | None,
        message: str,
        memory: DialogMemory | None = None,
    ) -> DialogDecision:
        memory = build_dialog_memory(
            user_id=user_id,
            chat_id=chat_id,
            memory=memory,
        )
        normalized_message = normalize_message(message)

        if not normalized_message:
            return self._remember_assistant_decision(
                memory=memory,
                user_message=message,
                action=ACTION_CLARIFICATION,
                assistant_message="Напишите, какой облачный сервис нужно подобрать.",
                clarification_questions=[
                    "Какая задача: база данных, Kubernetes, backend, object storage, backup, аналитика или ML?"
                ],
            )

        if is_pure_indifference_response(normalized_message) and memory.pending_fields:
            remember_ignored_fields(memory, memory.pending_fields)
            memory.pending_fields = []
            search_query = build_search_query(memory.slots)
            memory.last_search_query = search_query

            return self._remember_assistant_decision(
                memory=memory,
                user_message=message,
                action=ACTION_SEARCH,
                assistant_message=(
                    "Ок, тогда не буду ограничивать поиск по этим параметрам "
                    "и подберу варианты шире."
                ),
                search_query=search_query,
            )

        new_slots = self.slot_extractor.extract(message)

        if not memory.pending_fields and is_off_topic(normalized_message, slots=new_slots):
            return self._remember_assistant_decision(
                memory=memory,
                user_message=message,
                action=ACTION_OFF_TOPIC,
                assistant_message=build_off_topic_message(),
            )

        explicit_ignored_fields = detect_indifferent_fields(
            normalized_message=normalized_message,
            pending_fields=memory.pending_fields,
        )
        if explicit_ignored_fields:
            remember_ignored_fields(memory, explicit_ignored_fields)

        if should_start_new_request(memory=memory, new_slots=new_slots):
            memory.slots = DialogSlots()
            memory.pending_fields = []
            memory.ignored_fields = explicit_ignored_fields.copy()
            memory.last_search_query = None

        merge_slots(memory.slots, new_slots)
        missing_fields = get_missing_fields(memory, original_message=message)
        memory.pending_fields = missing_fields

        if missing_fields:
            questions = build_clarification_questions(missing_fields)
            return self._remember_assistant_decision(
                memory=memory,
                user_message=message,
                action=ACTION_CLARIFICATION,
                assistant_message=build_clarification_message(questions),
                clarification_questions=questions,
            )

        search_query = build_search_query(memory.slots, original_message=message)
        memory.last_search_query = search_query

        return self._remember_assistant_decision(
            memory=memory,
            user_message=message,
            action=ACTION_SEARCH,
            assistant_message="Данных достаточно, запускаю подбор облачных сервисов.",
            search_query=search_query,
        )

    def _remember_assistant_decision(
        self,
        memory: DialogMemory,
        user_message: str,
        action: str,
        assistant_message: str,
        clarification_questions: list[str] | None = None,
        search_query: str | None = None,
    ) -> DialogDecision:
        append_message(memory, role="user", content=user_message)
        append_message(memory, role="assistant", content=assistant_message)

        return DialogDecision(
            user_id=memory.user_id,
            chat_id=memory.chat_id,
            action=action,
            assistant_message=assistant_message,
            clarification_questions=clarification_questions or [],
            search_query=search_query,
            memory=memory,
        )


class DialogSlotExtractor:
    def extract(self, message: str) -> DialogSlots:
        raise NotImplementedError


class RuleBasedDialogSlotExtractor(DialogSlotExtractor):
    def extract(self, message: str) -> DialogSlots:
        return extract_dialog_slots(message)


class LLMFirstDialogSlotExtractor(DialogSlotExtractor):
    """
    Извлекает слоты диалога через LLM.

    Правила остаются запасным вариантом, чтобы локальные тесты и разработка
    не падали при недоступном LLM API.
    """

    def __init__(self, query_extractor: QueryExtractor | None = None) -> None:
        self.query_extractor = query_extractor

    def extract(self, message: str) -> DialogSlots:
        try:
            if self.query_extractor is None:
                self.query_extractor = QueryExtractor()

            structured_query = self.query_extractor.extract(message)
            return build_dialog_slots_from_structured_query(structured_query)
        except Exception:
            return extract_dialog_slots(message)


def build_dialog_slots_from_structured_query(
    structured_query: StructuredQuery,
) -> DialogSlots:
    request_type = structured_query.request_type
    service_area = structured_query.task_category

    components = {component.component for component in structured_query.required_components}

    if request_type == "solution_bundle":
        service_area = "solution_bundle"
    elif "managed_database" in components:
        service_area = "database"
    elif "kubernetes" in components:
        service_area = "kubernetes"
    elif "object_storage" in components:
        service_area = "object_storage"
    elif "backup" in components:
        service_area = "backup"
    elif "compute" in components:
        service_area = "compute" if service_area == "compute" else "backend"
    elif service_area == "web-hosting":
        service_area = "backend"

    db_engine = next(
        (
            component.db_engine
            for component in structured_query.required_components
            if component.db_engine
        ),
        None,
    )

    if db_engine is None:
        db_engine = detect_database_engine_from_technologies(structured_query.tech_stack)

    constraints = structured_query.constraints

    return DialogSlots(
        request_type=request_type,
        service_area=service_area,
        technologies=unique_values(structured_query.tech_stack),
        db_engine=db_engine,
        region=canonicalize_region(constraints.region),
        budget_max=constraints.budget_max,
    )


def append_message(memory: DialogMemory, role: str, content: str) -> None:
    memory.messages_count += 1


def build_dialog_memory(
    user_id: str,
    chat_id: str | None,
    memory: DialogMemory | None = None,
) -> DialogMemory:
    normalized_user_id = normalize_identifier(user_id, fallback="default")
    normalized_chat_id = normalize_identifier(
        chat_id or (memory.chat_id if memory else None) or str(uuid.uuid4()),
        fallback=str(uuid.uuid4()),
    )

    if memory is None:
        return DialogMemory(
            user_id=normalized_user_id,
            chat_id=normalized_chat_id,
        )

    copied_memory = memory.model_copy(deep=True)
    copied_memory.user_id = normalized_user_id
    copied_memory.chat_id = normalized_chat_id
    return copied_memory


def normalize_identifier(value: str | None, fallback: str) -> str:
    if value is None:
        return fallback

    normalized = value.strip()
    return normalized or fallback


def normalize_message(message: str) -> str:
    return " ".join(message.strip().lower().replace("ё", "е").split())


def extract_dialog_slots(message: str) -> DialogSlots:
    normalized = normalize_message(message)
    technologies = detect_technologies(normalized)
    db_engine = detect_database_engine(normalized)
    service_area = detect_service_area(normalized, technologies, db_engine)
    region = canonicalize_region(extract_region_from_text(message))
    budget_max = extract_budget_max(message)
    budget_period = extract_budget_period(message) if budget_max is not None else None

    return DialogSlots(
        service_area=service_area,
        technologies=technologies,
        db_engine=db_engine,
        region=region,
        budget_max=budget_max,
        budget_period=budget_period,
    )


def detect_technologies(normalized_message: str) -> list[str]:
    technologies = []

    technology_markers = {
        "kubernetes": ("kubernetes", "k8s", "кубер", "кубера", "куберу", "кубернетес"),
        "postgresql": (
            "postgresql",
            "postgres",
            "постгрес",
            "постгре",
            "постгрис",
            "постгрискл",
            "посгрискл",
            "посгрес",
            "постгресql",
        ),
        "mysql": ("mysql", "майскл", "мускул"),
        "clickhouse": ("clickhouse", "кликхаус"),
        "redis": ("redis", "редис"),
        "mongodb": ("mongodb", "mongo", "монго"),
        "django": ("django", "джанго"),
        "fastapi": ("fastapi", "фастапи"),
        "flask": ("flask", "фласк"),
        "python": ("python", "питон", "пайтон"),
        "s3": ("s3", "s3-хранилище", "s3 хранилище"),
        "object_storage": ("object storage", "объектное хранилище"),
    }

    for technology, markers in technology_markers.items():
        if any(marker in normalized_message for marker in markers):
            technologies.append(technology)

    return technologies


def detect_database_engine(normalized_message: str) -> str | None:
    return detect_database_engine_from_technologies(
        detect_technologies(normalized_message)
    )


def detect_database_engine_from_technologies(technologies: list[str]) -> str | None:
    for engine in ("postgresql", "mysql", "clickhouse", "redis", "mongodb"):
        if engine in technologies:
            return engine

    return None


def detect_service_area(
    normalized_message: str,
    technologies: list[str],
    db_engine: str | None,
) -> str | None:
    if "kubernetes" in technologies:
        return "kubernetes"

    if db_engine or any(
        marker in normalized_message
        for marker in ("база данных", "базу данных", "базы данных", "бд", "субд", "database")
    ):
        return "database"

    if any(
        marker in normalized_message
        for marker in ("object storage", "объектное хранилище", "хранилище", "s3")
    ):
        return "object_storage"

    if any(
        marker in normalized_message
        for marker in ("backend", "бекенд", "бэкенд", "сайт", "web", "django", "fastapi", "flask")
    ):
        return "backend"

    if any(
        marker in normalized_message
        for marker in ("сервер", "виртуальная машина", "vm", "vps", "compute")
    ):
        return "compute"

    if any(marker in normalized_message for marker in ("backup", "бэкап", "резервн")):
        return "backup"

    if any(marker in normalized_message for marker in ("аналитик", "bi", "etl", "clickhouse")):
        return "analytics"

    if any(marker in normalized_message for marker in ("ml", "machine learning", "ai")):
        return "ml"

    if any(
        marker in normalized_message
        for marker in ("облако", "облач", "сервис", "инфраструктур")
    ):
        return "unknown_cloud_task"

    return None


def extract_budget_max(normalized_message: str) -> float | None:
    normalized_message = normalize_message(normalized_message)

    if has_budget_indifference(normalized_message):
        return None

    if re.search(r"(?:за|на|бюджет)\s+один\s+руб", normalized_message):
        return 1.0

    patterns = (
        r"(?:до|максимум|не больше|не дороже)\s+(\d[\d\s]*(?:[.,]\d+)?)\s*(тысяч|тыс|к|k)?",
        r"(?:за|на|бюджет)\s+(\d[\d\s]*(?:[.,]\d+)?)\s*(тысяч|тыс|к|k)?\s*(?:руб|рублей|р)?",
        r"(\d[\d\s]*(?:[.,]\d+)?)\s*(тысяч|тыс|к|k)\s*(?:руб|рублей|р)?",
        r"(\d[\d\s]{3,})\s*(?:руб|рублей|р)",
    )

    for pattern in patterns:
        match = re.search(pattern, normalized_message)
        if not match:
            continue

        amount = float(match.group(1).replace(" ", "").replace(",", "."))
        multiplier = 1000 if len(match.groups()) > 1 and match.group(2) else 1
        return amount * multiplier

    return None


def extract_budget_period(message: str) -> str | None:
    normalized_message = normalize_message(message)

    if re.search(r"(?:в|за|на)\s+(?:час|1\s*час|ч)\b|/час|руб/?час", normalized_message):
        return "hour"

    if re.search(r"(?:в|за|на)\s+(?:день|сутки|суток)\b|/день|/сут", normalized_message):
        return "day"

    if re.search(r"(?:в|за|на)\s+(?:неделю|недели|неделя)\b|/нед", normalized_message):
        return "week"

    if re.search(r"(?:в|за|на)\s+(?:месяц|мес)\b|/мес|руб/?мес", normalized_message):
        return "month"

    return "month"


def merge_slots(current: DialogSlots, new_slots: DialogSlots) -> None:
    if new_slots.request_type:
        current.request_type = new_slots.request_type

    if new_slots.service_area:
        current.service_area = new_slots.service_area

    for technology in new_slots.technologies:
        if technology not in current.technologies:
            current.technologies.append(technology)

    if new_slots.db_engine:
        current.db_engine = new_slots.db_engine

    if new_slots.region:
        current.region = new_slots.region

    if new_slots.budget_max is not None:
        current.budget_max = new_slots.budget_max
        current.budget_period = new_slots.budget_period or "month"


def should_start_new_request(memory: DialogMemory, new_slots: DialogSlots) -> bool:
    if memory.pending_fields:
        return False

    if memory.last_search_query and new_slots.service_area is not None:
        return True

    if memory.slots.service_area is None:
        return False

    if new_slots.service_area is None:
        return False

    return new_slots.service_area != memory.slots.service_area


def get_missing_fields(memory: DialogMemory, original_message: str) -> list[str]:
    slots = memory.slots
    ignored = set(memory.ignored_fields)
    missing = []
    short_query = len(normalize_message(original_message).split()) <= 4

    if slots.service_area is None and FIELD_TASK not in ignored:
        missing.append(FIELD_TASK)
        return missing

    if slots.request_type == "solution_bundle" and not short_query:
        return []

    if slots.service_area == "unknown_cloud_task" and FIELD_TASK not in ignored:
        missing.append(FIELD_TASK)

    if slots.service_area == "database" and not slots.db_engine and FIELD_DATABASE_ENGINE not in ignored:
        missing.append(FIELD_DATABASE_ENGINE)

    if slots.service_area == "backend" and not slots.technologies and FIELD_TECH_STACK not in ignored:
        missing.append(FIELD_TECH_STACK)

    should_ask_soft_fields = bool(missing) or (
        short_query and slots.budget_max is None
    )

    if should_ask_soft_fields and not slots.region and FIELD_REGION not in ignored:
        missing.append(FIELD_REGION)

    if should_ask_soft_fields and slots.budget_max is None and FIELD_BUDGET not in ignored:
        missing.append(FIELD_BUDGET)

    return unique_values(missing)


def build_clarification_questions(missing_fields: list[str]) -> list[str]:
    questions_by_field = {
        FIELD_TASK: (
            "Какая облачная задача нужна: база данных, Kubernetes, backend, "
            "object storage, backup, аналитика или ML?"
        ),
        FIELD_DATABASE_ENGINE: (
            "Какая база данных нужна: PostgreSQL, MySQL, ClickHouse, Redis, MongoDB или другая?"
        ),
        FIELD_TECH_STACK: (
            "Какой стек технологий у приложения: Python/Django/FastAPI, Node.js, Java или другой?"
        ),
        FIELD_REGION: "В каком регионе нужен сервис? Например: Москва. Можно ответить: любой.",
        FIELD_BUDGET: "Есть ли бюджет в месяц? Например: до 20000 рублей. Можно ответить: мне все равно.",
    }

    return [
        questions_by_field[field]
        for field in missing_fields
        if field in questions_by_field
    ]


def build_clarification_message(questions: list[str]) -> str:
    if not questions:
        return "Мне нужно чуть больше данных, чтобы подобрать облачный сервис."

    return (
        "Мне нужно уточнить несколько параметров, чтобы подобрать нормальные варианты. "
        "Если какой-то параметр не важен, можно ответить: мне все равно."
    )


def build_search_query(slots: DialogSlots, original_message: str | None = None) -> str:
    if should_preserve_original_query(original_message, slots):
        return original_message.strip()

    parts = []

    if slots.service_area == "database":
        parts.append("нужна база данных")
    elif slots.service_area == "solution_bundle":
        parts.append("нужна связка облачных сервисов")
    elif slots.service_area == "kubernetes":
        parts.append("нужен kubernetes сервис")
    elif slots.service_area == "object_storage":
        parts.append("нужно объектное хранилище")
    elif slots.service_area == "backend":
        parts.append("нужен сервис для backend приложения")
    elif slots.service_area == "compute":
        parts.append("нужен облачный сервер или виртуальная машина")
    elif slots.service_area == "backup":
        parts.append("нужен backup сервис")
    elif slots.service_area == "analytics":
        parts.append("нужен сервис для аналитики")
    elif slots.service_area == "ml":
        parts.append("нужен сервис для ML")
    else:
        parts.append("нужен облачный сервис")

    if slots.db_engine:
        parts.append(slots.db_engine)

    for technology in sorted(slots.technologies):
        if technology != slots.db_engine:
            parts.append(technology)

    if slots.region:
        parts.append(f"в регионе {slots.region}")

    if slots.budget_max is not None:
        period = slots.budget_period or "month"
        period_text = {
            "hour": "в час",
            "day": "в день",
            "week": "в неделю",
            "month": "в месяц",
        }.get(period, "в месяц")
        parts.append(f"бюджет до {int(slots.budget_max)} рублей {period_text}")

    return " ".join(parts)


def should_preserve_original_query(
    original_message: str | None,
    slots: DialogSlots,
) -> bool:
    if original_message is None:
        return False

    normalized = normalize_message(original_message)
    words = normalized.split()

    if len(words) < 8:
        return False

    if slots.request_type == "solution_bundle":
        return True

    cloud_markers = [
        "backend",
        "бекенд",
        "бэкенд",
        "сервер",
        "виртуальная машина",
        "vm",
        "vps",
        "python",
        "postgresql",
        "postgres",
        "база данных",
        "хранение",
        "изображен",
        "s3",
        "object storage",
        "backup",
        "бэкап",
        "резервн",
        "масштаб",
        "load balancer",
        "балансиров",
        "kubernetes",
        "кубер",
    ]
    matched_markers = [
        marker
        for marker in cloud_markers
        if marker in normalized
    ]

    if len(matched_markers) >= 2:
        return True

    return (
        slots.service_area is not None
        and bool(slots.region or slots.budget_max or slots.technologies)
    )


def build_search_signature(message: str) -> tuple[Any, ...]:
    slots = extract_dialog_slots(message)

    return (
        slots.service_area,
        tuple(sorted(slots.technologies)),
        slots.db_engine,
        slots.region,
        slots.budget_max,
    )


def is_indifference(normalized_message: str) -> bool:
    markers = (
        "все равно",
        "всё равно",
        "мне все равно",
        "мне всё равно",
        "без разницы",
        "не важно",
        "неважно",
        "любой",
        "любая",
        "любое",
        "как угодно",
        "нет ограничений",
    )
    return any(marker in normalized_message for marker in markers)


def is_pure_indifference_response(normalized_message: str) -> bool:
    if not is_indifference(normalized_message):
        return False

    extra_slots = extract_dialog_slots(normalized_message)
    if (
        extra_slots.service_area
        or extra_slots.technologies
        or extra_slots.db_engine
        or extra_slots.region
        or extra_slots.budget_max is not None
    ):
        return False

    return normalized_message in {
        "все равно",
        "всё равно",
        "мне все равно",
        "мне всё равно",
        "без разницы",
        "не важно",
        "неважно",
        "любой",
        "любая",
        "любое",
        "как угодно",
        "нет ограничений",
    }


def detect_indifferent_fields(
    normalized_message: str,
    pending_fields: list[str],
) -> list[str]:
    ignored_fields = []

    if has_budget_indifference(normalized_message):
        ignored_fields.append(FIELD_BUDGET)

    if has_region_indifference(normalized_message):
        ignored_fields.append(FIELD_REGION)

    if is_pure_indifference_response(normalized_message):
        ignored_fields.extend(pending_fields)

    return unique_values(ignored_fields)


def has_budget_indifference(normalized_message: str) -> bool:
    return any(
        marker in normalized_message
        for marker in (
            "без бюджета",
            "любой бюджет",
            "бюджет любой",
            "бюджет не важен",
            "бюджет неважен",
            "бюджет мне все равно",
            "по бюджету все равно",
            "по бюджету всё равно",
        )
    )


def has_region_indifference(normalized_message: str) -> bool:
    return any(
        marker in normalized_message
        for marker in (
            "любой регион",
            "регион любой",
            "регион не важен",
            "регион неважен",
            "где угодно",
        )
    )


def remember_ignored_fields(memory: DialogMemory, fields: list[str]) -> None:
    for field in fields:
        if field not in memory.ignored_fields:
            memory.ignored_fields.append(field)


def is_off_topic(normalized_message: str, slots: DialogSlots | None = None) -> bool:
    if not normalized_message:
        return False

    slots = slots or extract_dialog_slots(normalized_message)
    if slots.service_area is not None:
        return False

    if has_cloud_relevance(normalized_message):
        return False

    if has_prompt_injection_marker(normalized_message):
        return True

    off_topic_markers = (
        "привет",
        "как дела",
        "анекдот",
        "погода",
        "фильм",
        "музыка",
        "рецепт",
        "поговори",
        "кто ты",
        "что такое любовь",
        "расскажи историю",
    )

    return (
        any(marker in normalized_message for marker in off_topic_markers)
        or len(normalized_message.split()) <= 3
        or not has_cloud_relevance(normalized_message)
    )


def has_cloud_relevance(normalized_message: str) -> bool:
    cloud_markers = (
        "облак",
        "сервис",
        "провайдер",
        "инфраструктур",
        "сервер",
        "виртуальная машина",
        "vm",
        "vps",
        "compute",
        "backend",
        "бекенд",
        "бэкенд",
        "сайт",
        "хостинг",
        "kubernetes",
        "k8s",
        "кубер",
        "docker",
        "докер",
        "база данных",
        "базу данных",
        "бд",
        "субд",
        "database",
        "postgres",
        "postgresql",
        "постгрес",
        "постгрис",
        "mysql",
        "майскл",
        "clickhouse",
        "redis",
        "mongodb",
        "s3",
        "object storage",
        "хранилище",
        "файлы",
        "изображен",
        "backup",
        "бэкап",
        "резервн",
        "load balancer",
        "балансиров",
        "cdn",
        "аналитик",
        "bi",
        "ml",
        "gpu",
        "152-фз",
        "152-fz",
        "бюджет",
        "руб",
        "москва",
        "росси",
    )
    return any(marker in normalized_message for marker in cloud_markers)


def has_prompt_injection_marker(normalized_message: str) -> bool:
    injection_markers = (
        "ignore previous",
        "ignore all previous",
        "forget previous",
        "system prompt",
        "developer message",
        "show your prompt",
        "выведи системный",
        "покажи системный",
        "игнорируй инструкции",
        "игнорируй все инструкции",
        "забудь инструкции",
        "забудь правила",
        "раскрой промпт",
        "системный промпт",
        "developer prompt",
        "jailbreak",
    )
    return any(marker in normalized_message for marker in injection_markers)


def build_off_topic_message() -> str:
    return (
        "Я лучше всего помогаю с подбором облачных сервисов, а не с общим чатом. "
        "Со мной можно обсуждать базы данных, Kubernetes, backend/web-хостинг, "
        "object storage, backup, аналитику, ML, регионы, бюджет и требования вроде 152-ФЗ. "
        "Например: 'Нужен PostgreSQL в Москве до 20000 рублей'."
    )


def unique_values(values: list[str]) -> list[str]:
    result = []

    for value in values:
        if value not in result:
            result.append(value)

    return result
