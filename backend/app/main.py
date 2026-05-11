from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.chat import ChatApiResponse, ChatRequest, chat_with_agent
from backend.app.api.search import (
    CatalogResponse,
    CatalogSearchResponse,
    CatalogServiceCard,
    EmptySearchQueryError,
    SearchApiResponse,
    SearchRequest,
    get_catalog_service_details,
    get_catalog,
    search_catalog_services,
    search_cloud_services,
)


app = FastAPI(
    title="Cloud Marketplace API",
    description="API для подбора облачных сервисов по пользовательскому запросу.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Cloud Marketplace API",
        "chat": "POST /api/chat",
        "search": "POST /api/search",
        "catalog": "GET /api/catalog",
        "catalog_search": "GET /api/catalog/search",
        "health": "GET /health",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/search", response_model=SearchApiResponse)
def search(request: SearchRequest) -> SearchApiResponse:
    try:
        return search_cloud_services(
            query=request.query,
            with_explanation=request.with_explanation,
            include_debug=request.include_debug,
        )
    except EmptySearchQueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/chat", response_model=ChatApiResponse)
def chat(request: ChatRequest) -> ChatApiResponse:
    try:
        return chat_with_agent(request)
    except EmptySearchQueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/catalog", response_model=CatalogResponse)
def catalog() -> CatalogResponse:
    return get_catalog()


@app.get("/api/catalog/search", response_model=CatalogSearchResponse)
def catalog_search(
    q: str | None = Query(default=None, description="Текст поиска по витрине"),
    provider_id: str | None = Query(default=None, description="Фильтр по provider_id"),
    category: str | None = Query(default=None, description="Фильтр по категории сервиса"),
    region: str | None = Query(default=None, description="Фильтр по региону"),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    pricing_limit: int = Query(default=5, ge=0, le=50),
) -> CatalogSearchResponse:
    return search_catalog_services(
        query=q,
        provider_id=provider_id,
        category=category,
        region=region,
        limit=limit,
        offset=offset,
        pricing_limit=pricing_limit,
    )


@app.get("/api/catalog/services/{service_id}", response_model=CatalogServiceCard)
def catalog_service(
    service_id: str,
    pricing_limit: int = Query(default=50, ge=0, le=300),
) -> CatalogServiceCard:
    try:
        return get_catalog_service_details(
            service_id=service_id,
            pricing_limit=pricing_limit,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
