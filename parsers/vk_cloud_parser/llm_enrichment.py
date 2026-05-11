from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.llm_client import ask_llm


_VALID_CATEGORIES = {
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
    "Cloud Service",
}

_SYSTEM_PROMPT = """\
Ты эксперт по облачным сервисам. Классифицируй и опиши облачный сервис для каталога.
Отвечай ТОЛЬКО валидным JSON без markdown-обёртки.
"""

_USER_TEMPLATE = """\
Сервис: {service_name}
Документ/раздел прайс-листа: {title}
Провайдер: VK Cloud (российский облачный провайдер)

Верни JSON со следующими полями:
- category: одна из категорий: "Cloud Compute", "Cloud Storage", "Database", "Network", \
"Containers and Serverless", "Messaging and Cache", "Security", "Data and Analytics", \
"Monitoring and DevOps", "Developer Tools", "Cloud Service"
- description: 1-2 предложения на русском языке — что делает сервис и для каких задач используется
- tech_stack_tags: список 3-6 технологических тегов (например ["Kubernetes", "S3", "SQL"])
- use_case_tags: список 2-4 тегов сценариев использования в kebab-case (например ["backup", "web-hosting"])
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def enrich_service_with_llm(service_name: str, title: str = "") -> dict[str, Any]:
    prompt = _USER_TEMPLATE.format(service_name=service_name, title=title or service_name)
    raw = ask_llm(_SYSTEM_PROMPT, prompt)
    data = _extract_json(raw)

    category = data.get("category", "Cloud Service")
    if category not in _VALID_CATEGORIES:
        category = "Cloud Service"

    return {
        "category": category,
        "description": str(data.get("description", "")),
        "tech_stack_tags": sorted(set(str(x) for x in data.get("tech_stack_tags", []))),
        "use_case_tags": sorted(set(str(x) for x in data.get("use_case_tags", []))),
    }


def enrich_service_rule_based(service_name: str) -> dict[str, Any]:
    """Emergency fallback only. Main path should use enrich_service_with_llm()."""
    text = service_name.lower()
    if any(x in text for x in ["server", "compute", "vm", "cloud servers", "gpu"]):
        category = "Cloud Compute"
        tags = ["VM", "IaaS", "Compute"]
        use = ["web-hosting", "application-hosting"]
    elif any(x in text for x in ["storage", "s3", "volume", "backup", "disk"]):
        category = "Cloud Storage"
        tags = ["Storage", "S3", "Backup"]
        use = ["backup", "data-storage"]
    elif any(x in text for x in ["database", "sql", "postgres", "mysql", "redis", "mongo"]):
        category = "Database"
        tags = ["Database", "SQL", "NoSQL"]
        use = ["database", "backend"]
    elif any(x in text for x in ["kubernetes", "container"]):
        category = "Containers and Serverless"
        tags = ["Kubernetes", "Containers", "Docker"]
        use = ["container-orchestration", "devops"]
    elif any(x in text for x in ["cdn", "network", "ip", "dns", "vpn", "load", "balancer"]):
        category = "Network"
        tags = ["Network", "IP", "Traffic"]
        use = ["networking", "web-hosting"]
    elif any(x in text for x in ["kafka", "rabbit", "queue", "message"]):
        category = "Messaging and Cache"
        tags = ["Queue", "Kafka", "Messaging"]
        use = ["message-broker", "microservices"]
    else:
        category = "Cloud Service"
        tags = ["Cloud", "VK Cloud"]
        use = ["cloud-service"]
    return {
        "category": category,
        "description": f"Облачный сервис VK Cloud: {service_name}. Используется для сценариев: {', '.join(use)}.",
        "tech_stack_tags": tags,
        "use_case_tags": use,
    }


def enrich_pricing_item_rule_based(item_name: str, service_name: str = "") -> dict[str, Any]:
    text = f"{service_name} {item_name}".lower()
    checks = [
        ("cpu_ram_vm", ["cloud servers", "виртуаль", "server", "сервер", "vm", "vcpu", "cpu", "ram", "gpu"]),
        ("storage", ["storage", "хран", "volume", "disk", "диск", "s3", "snapshot", "backup", "бэкап"]),
        ("traffic", ["traffic", "трафик", "download", "upload", "исходящ", "входящ", "cdn"]),
        ("request", ["api", "запрос", "request", "requests", "операц"]),
        ("database_instance", ["database", "postgres", "mysql", "sql", "mongodb", "redis", "clickhouse", "db"]),
        ("network", ["ip", "dns", "nat", "vpn", "load", "balance", "balancer", "сеть", "network"]),
        ("security", ["firewall", "waf", "security", "защит", "сертификат", "key", "kms"]),
        ("container", ["kubernetes", "container", "docker", "cluster", "node", "контейнер"]),
        ("message_queue", ["kafka", "rabbitmq", "queue", "message", "очеред"]),
        ("monitoring", ["monitoring", "монитор", "log", "лог", "metric", "метрик"]),
    ]
    item_type = "other"
    for candidate, words in checks:
        if any(w in text for w in words):
            item_type = candidate
            break

    tags = set()
    for token in ["vcpu", "cpu", "ram", "gpu", "ssd", "hdd", "s3", "api", "backup", "redis", "kafka",
                  "rabbitmq", "postgresql", "postgres", "mysql", "kubernetes", "vpc", "ip", "vpn", "cdn"]:
        if token in text:
            tags.add(token.upper() if token in {"api", "ssd", "hdd", "gpu", "ram", "vpc", "ip", "vpn", "cdn"} else token)
    tags.add(item_type)

    size_tags = re.findall(r"\b\d+\s*(?:vcpu|cpu|гб|gb|тб|tb|мбит|mbit)\b", text)
    tags.update(size_tags)

    return {
        "item_type": item_type,
        "configuration_tags": sorted(tags),
    }
