from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.llm_client import ask_llm
from app.utils import clean_text


def _parse_llm_json(raw: str) -> dict:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)

CATEGORIES = [
    "Cloud Compute",
    "Cloud Storage",
    "Database",
    "Network",
    "Containers and Serverless",
    "Messaging and Cache",
    "Security",
    "Data and Analytics",
    "Monitoring and DevOps",
    "Developer Tools",
    "Dedicated Servers",
    "Colocation",
    "Cloud Service",
]


def rule_based_category(name: str) -> str:
    s = name.lower()
    if any(x in s for x in ["выделенные сервер", "серверы с gpu", "облачные сервер", "приватный хост", "vmware", "vdc"]):
        return "Cloud Compute"
    if any(x in s for x in ["s3", "хранилище", "storage", "диск", "резервное копирование", "backup"]):
        return "Cloud Storage"
    if any(x in s for x in ["базы данных", "dbaas", "postgres", "mysql", "redis", "clickhouse"]):
        return "Database"
    if any(x in s for x in ["kubernetes", "container", "registry", "контейнер"]):
        return "Containers and Serverless"
    if any(x in s for x in ["сеть", "direct", "cdn", "dns", "ip", "подсеть", "балансировщик", "порт"]):
        return "Network"
    if any(x in s for x in ["защит", "ddos", "waf", "usergate", "firewall", "межсет", "сзи", "гост vpn"]):
        return "Security"
    if any(x in s for x in ["data", "spark", "trino", "аналит"]):
        return "Data and Analytics"
    if any(x in s for x in ["размещение оборудования", "colocation"]):
        return "Colocation"
    return "Cloud Service"


def rule_based_tags(name: str, category: str) -> tuple[list[str], list[str]]:
    s = name.lower()
    tech: set[str] = set()
    use: set[str] = set()

    if category == "Cloud Compute":
        tech.update(["CPU", "RAM", "VM", "Linux", "Windows"])
        use.update(["web-applications", "backend", "test-stand", "corporate-services"])
    if category == "Cloud Storage":
        tech.update(["Storage", "S3", "Backup"])
        use.update(["backup", "data-storage", "media-storage"])
    if category == "Database":
        tech.update(["SQL", "PostgreSQL", "MySQL", "Redis"])
        use.update(["database-hosting", "application-development", "analytics-systems"])
    if category == "Containers and Serverless":
        tech.update(["Docker", "Kubernetes", "Container Registry"])
        use.update(["microservices", "devops", "application-deployment"])
    if category == "Network":
        tech.update(["IP", "Network", "Load Balancer", "Direct Connect"])
        use.update(["network-connectivity", "traffic-routing", "hybrid-cloud"])
    if category == "Security":
        tech.update(["Security", "WAF", "DDoS", "Firewall"])
        use.update(["secure-infrastructure", "compliance", "threat-protection"])

    if "gpu" in s:
        tech.add("GPU")
        use.add("machine-learning")
    if "152" in s or "аттест" in s or "а-цод" in s:
        tech.add("152-FZ")
        use.add("personal-data-processing")

    return sorted(tech), sorted(use)


def enrich_service_with_llm(service_name: str, raw_hint: str = "") -> dict[str, Any]:
    fallback_category = rule_based_category(service_name)
    fallback_tech, fallback_use = rule_based_tags(service_name, fallback_category)
    fallback = {
        "category": fallback_category,
        "description": f"Сервис Selectel «{clean_text(service_name)}» используется для облачной инфраструктуры и связанных с ней задач.",
        "tech_stack_tags": fallback_tech,
        "use_case_tags": fallback_use,
    }

    system = (
        "Ты нормализуешь облачные сервисы Selectel для marketplace cloud services. "
        "Верни строго JSON: description, category, tech_stack_tags, use_case_tags. "
        f"category выбери из списка: {', '.join(CATEGORIES)}. "
        "description — 1-2 предложения на русском языке, без рекламы. "
        "tech_stack_tags и use_case_tags — только на английском языке в kebab-case, "
        "например: [\"S3\", \"Kubernetes\", \"PostgreSQL\"] и [\"backup\", \"web-hosting\", \"machine-learning\"]. "
        "Никаких русских слов в тегах."
    )
    user = f"Название сервиса: {service_name}\nСырой контекст: {raw_hint[:1500]}"
    raw = ask_llm(system, user)
    if not raw:
        return fallback
    try:
        data = _parse_llm_json(raw)
    except (json.JSONDecodeError, ValueError):
        return fallback

    category = data.get("category") if data.get("category") in CATEGORIES else fallback_category
    return {
        "category": category,
        "description": clean_text(data.get("description") or fallback["description"]),
        "tech_stack_tags": data.get("tech_stack_tags") if isinstance(data.get("tech_stack_tags"), list) else fallback_tech,
        "use_case_tags": data.get("use_case_tags") if isinstance(data.get("use_case_tags"), list) else fallback_use,
    }
