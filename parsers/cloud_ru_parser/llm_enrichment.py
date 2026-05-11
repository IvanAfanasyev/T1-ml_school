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
Документ: {title}
Провайдер: Cloud.ru Advanced (российский облачный провайдер)

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
    # strip markdown code fences if present
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
        "tech_stack_tags": sorted(set(data.get("tech_stack_tags", []))),
        "use_case_tags": sorted(set(data.get("use_case_tags", []))),
    }


def enrich_pricing_item_rule_based(item_name: str, service_name: str = "") -> dict[str, Any]:
    text = f"{service_name} {item_name}".lower()
    checks = [
        ("cpu_ram_vm", ["виртуальная машина", "ecs", "vcpu", "ram", "gpu"]),
        ("storage", ["storage", "хран", "volume", "sfs", "obs", "size", "snapshot", "backup"]),
        ("traffic", ["traffic", "трафик", "download", "upload", "исходящ", "входящ"]),
        ("request", ["api", "запрос", "вызовы", "put", "get", "delete"]),
        ("database_instance", ["database", "postgres", "mysql", "sqlserver", "mongodb", "redis"]),
        ("network", ["ip", "vpc", "nat", "vpn", "load balance", "direct connect", "router"]),
        ("security", ["firewall", "waf", "bastion", "certificate", "encryption", "security"]),
        ("container", ["kubernetes", "container", "cce", "cluster", "node"]),
        ("message_queue", ["kafka", "rabbitmq", "rocketmq", "message"]),
        ("monitoring", ["monitoring", "apm", "aom", "trace", "cloud eye"]),
    ]
    item_type = "other"
    for candidate, words in checks:
        if any(w in text for w in words):
            item_type = candidate
            break

    tags = set()
    for token in ["vcpu", "ram", "gpu", "ssd", "hdd", "s3", "api", "backup", "redis", "kafka",
                  "rabbitmq", "postgresql", "mysql", "kubernetes", "vpc", "ip", "vpn"]:
        if token in text:
            tags.add(token.upper() if token in {"api", "ssd", "hdd", "gpu", "ram", "vpc", "ip", "vpn"} else token)
    tags.add(item_type)

    size_tags = re.findall(r"\b\d+\s*(?:vcpu|гб|gb|тб|tb)\b", text)
    tags.update(size_tags)

    return {
        "item_type": item_type,
        "configuration_tags": sorted(tags),
    }
