from pydantic import BaseModel, Field


class GoldenDatasetItem(BaseModel):
    query_id: str
    query: str

    relevant_service_ids: list[str] = Field(default_factory=list)

    # Главный ожидаемый сервис.
    # Используем для MRR и удобного анализа.
    primary_service_id: str | None = None

    notes: str | None = None


class QueryEvaluationResult(BaseModel):
    query_id: str
    query: str

    expected_service_ids: list[str]
    retrieved_service_ids: list[str]

    precision_at_3: float
    reciprocal_rank: float

    first_relevant_rank: int | None = None
    primary_service_rank: int | None = None