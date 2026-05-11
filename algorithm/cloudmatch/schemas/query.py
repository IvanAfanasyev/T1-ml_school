from typing import Any, Optional

from pydantic import BaseModel, Field


class RequiredComponent(BaseModel):
    """
    Компонент решения, который нужен пользователю.

    Примеры:
    - compute
    - managed_database
    - object_storage
    - kubernetes
    - backup
    - analytics
    """

    component: str
    required: bool = True

    # Дополнительная конкретизация компонента.
    # Например:
    # object_storage + subtype = s3
    subtype: Optional[str] = None

    # Для баз данных.
    # Например:
    # managed_database + db_engine = postgresql
    db_engine: Optional[str] = None

    reason: Optional[str] = None


class QueryRequirement(BaseModel):
    """
    Универсальное требование пользователя.

    Сюда складываем критерии, которые не хотим заранее
    жёстко прописывать отдельными полями.

    Примеры:
    - support_level = 24/7
    - billing_period = month
    - gpu_required = true
    - pricing_model = pay-as-you-go
    """

    name: str
    value: Any

    required: bool = False
    confidence: float = 1.0
    source_text: Optional[str] = None
    reason: Optional[str] = None


class QueryConstraints(BaseModel):
    """
    Частые ограничения, которые удобно держать отдельно.
    """

    region: Optional[str] = None
    region_required: bool = False
    effective_region: Optional[str] = None
    nearby_regions: list[str] = Field(default_factory=list)
    region_fallback_used: bool = False
    region_fallback_reason: Optional[str] = None

    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    budget_required: bool = False
    budget_period: Optional[str] = None

    # 152-ФЗ обязателен всегда.
    compliance_required: bool = True
    compliance_tags: list[str] = Field(default_factory=lambda: ["152-FZ"])

    # Дополнительные ограничения, если они появятся.
    additional: list[QueryRequirement] = Field(default_factory=list)


class StructuredQuery(BaseModel):
    """
    Итоговая структура пользовательского запроса.
    """

    raw_query: str

    # single_service: обычный top-3 по одной задаче.
    # solution_bundle: связка из нескольких инфраструктурных компонентов.
    request_type: Optional[str] = None

    task_category: Optional[str] = None
    intent: Optional[str] = None

    tech_stack: list[str] = Field(default_factory=list)
    use_case: list[str] = Field(default_factory=list)

    required_components: list[RequiredComponent] = Field(default_factory=list)

    constraints: QueryConstraints = Field(default_factory=QueryConstraints)

    # Дополнительные требования пользователя.
    requirements: list[QueryRequirement] = Field(default_factory=list)

    # Сырые извлечённые сущности, если захотим сохранить всё.
    extracted_entities: list[QueryRequirement] = Field(default_factory=list)

    confidence: float = 0.0
