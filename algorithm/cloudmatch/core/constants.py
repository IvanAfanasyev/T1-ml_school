# Веса для retrieval:
EMBEDDING_WEIGHT = 0.7
BM25_WEIGHT = 0.3

# Веса для финального score:
RETRIEVAL_WEIGHT = 0.7
ENTITY_MATCH_WEIGHT = 0.3

# 152-ФЗ обязателен всегда.
REQUIRED_COMPLIANCE_TAG = "152-FZ"

TOP_K_RECOMMENDATIONS = 3
RETRIEVAL_SERVICE_CANDIDATES_LIMIT = 30
PRICING_ITEMS_PER_SERVICE_LIMIT = 5

PROVIDERS_FILE = "data/normalized/providers.json"
SERVICES_FILE = "data/normalized/services.json"
PRICING_ITEMS_FILE = "data/normalized/service_pricing_items.json"

# Индексы для embedding-поиска.
SERVICE_EMBEDDINGS_FILE = "data/indexes/service_embeddings.npy"
SERVICE_IDS_FILE = "data/indexes/service_ids.json"

# Модель для локальных embeddings.
# Для MVP берём мультиязычную модель, потому что данные и запросы могут быть на русском и английском.
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

BUDGET_WITHIN = "within_budget"
BUDGET_OVER = "over_budget"
BUDGET_UNKNOWN = "price_unknown"
BUDGET_NOT_SPECIFIED = "budget_not_specified"