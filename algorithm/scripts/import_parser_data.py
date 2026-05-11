import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from algorithm.cloudmatch.geo.region_resolver import canonicalize_region, normalize_location_key


PROVIDER_DIRS = ("cloud-ru", "selectel", "t1-cloud", "vk-cloud")


def main() -> None:
    args = parse_args()
    source_dir = Path(args.source_dir).expanduser()
    output_dir = Path(args.output_dir)

    import_parser_data(
        source_dir=source_dir,
        output_dir=output_dir,
        clean=not args.no_clean,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Import final parser JSON files into the project normalized "
            "data structure."
        )
    )
    parser.add_argument(
        "--source-dir",
        default="~/Downloads/Telegram Desktop/data",
        help="Directory with providers.json and provider subdirectories.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/normalized",
        help="Project normalized data directory.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove legacy generated normalized subdirectories.",
    )
    return parser.parse_args()


def import_parser_data(source_dir: Path, output_dir: Path, clean: bool = True) -> None:
    if clean:
        clean_legacy_outputs(output_dir)

    providers = [
        normalize_provider(item)
        for item in read_json_list(source_dir / "providers.json")
    ]

    services = []
    pricing_items = []
    parse_log = []

    for provider_id in PROVIDER_DIRS:
        provider_dir = source_dir / provider_id
        provider_services = [
            normalize_service(item)
            for item in read_json_list(provider_dir / "services.json")
        ]
        services.extend(provider_services)

        provider_pricing_items = [
            normalize_pricing_item(item)
            for item in read_json_list(provider_dir / "service_pricing_items.json")
        ]
        pricing_items.extend(provider_pricing_items)

        parse_log.extend(
            normalize_parse_log_item(provider_id, item)
            for item in read_json_list(provider_dir / "parse_log.json")
            if not is_user_task_template_log(item)
        )

    service_ids = {service["service_id"] for service in services}
    pricing_items = [
        item
        for item in pricing_items
        if item["service_id"] in service_ids
    ]

    write_json(output_dir / "providers.json", providers)
    write_json(output_dir / "services.json", services)
    write_json(output_dir / "service_pricing_items.json", pricing_items)
    write_json(output_dir / "parse_log.json", parse_log)
    write_json(output_dir / "errors.json", [])

    print("Imported normalized parser data:")
    print(f"- providers: {len(providers)}")
    print(f"- services: {len(services)}")
    print(f"- service_pricing_items: {len(pricing_items)}")
    print(f"- parse_log: {len(parse_log)}")
    print(f"- output_dir: {output_dir}")


def clean_legacy_outputs(output_dir: Path) -> None:
    for path in (
        output_dir / "providers",
        output_dir / "services",
    ):
        if path.exists():
            shutil.rmtree(path)

    user_task_templates = output_dir / "user_task_templates.json"
    if user_task_templates.exists():
        user_task_templates.unlink()


def read_json_list(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list")

    result = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(f"{path} must contain only JSON objects")
        result.append(item)

    return result


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_provider(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_id": required_text(item, "provider_id"),
        "name": required_text(item, "name"),
        "base_platform": optional_text(item.get("base_platform")),
        "is_152fz_compliant": bool(item.get("is_152fz_compliant", False)),
        "regions": normalize_regions(item.get("regions")),
        "api_docs_url": optional_text(item.get("api_docs_url")),
        "pricing_url": optional_text(item.get("pricing_url")),
        "source_url": first_text(
            item.get("source_url"),
            item.get("pricing_url"),
            item.get("api_docs_url"),
            item.get("certificate_url"),
        ),
        "parsed_at": first_text(item.get("parsed_at")),
    }


def normalize_service(item: dict[str, Any]) -> dict[str, Any]:
    source_url = first_text(
        item.get("source_url"),
        item.get("service_url"),
        item.get("tariff_index_url"),
        item.get("availability_source_url"),
        item.get("compliance_source_url"),
    )
    service_url = first_text(
        item.get("service_url"),
        source_url,
    )

    price_from_rub = item.get("price_from_rub")
    if price_from_rub is None:
        price_from_rub = item.get("price_from_value")

    return {
        "service_id": required_text(item, "service_id"),
        "provider_id": required_text(item, "provider_id"),
        "name": first_text(item.get("name"), item.get("service_id")),
        "category": first_text(item.get("category"), "Other"),
        "description": first_text(item.get("description"), item.get("name")),
        "tech_stack_tags": normalize_string_list(item.get("tech_stack_tags")),
        "use_case_tags": normalize_string_list(item.get("use_case_tags")),
        "compliance_tags": normalize_string_list(item.get("compliance_tags")),
        "regions": normalize_regions(item.get("regions")),
        "pricing_model": optional_text(item.get("pricing_model")),
        "price_from_rub": price_from_rub,
        "price_unit": optional_text(item.get("price_unit")),
        "support_level": optional_text(item.get("support_level")),
        "service_url": service_url,
        "source_url": source_url,
        "parsed_at": first_text(item.get("parsed_at")),
        "is_synthetic": bool(item.get("is_synthetic", False)),
    }


def normalize_pricing_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "pricing_item_id": required_text(item, "pricing_item_id"),
        "service_id": required_text(item, "service_id"),
        "provider_id": required_text(item, "provider_id"),
        "item_name": first_text(item.get("item_name"), item.get("pricing_item_id")),
        "item_type": first_text(item.get("item_type"), "unknown"),
        "price_rub": item.get("price_rub"),
        "price_unit": optional_text(item.get("price_unit")),
        "billing_period": optional_text(item.get("billing_period")),
        "region": normalize_region(item.get("region")),
        "configuration_tags": normalize_string_list(item.get("configuration_tags")),
        "source_url": first_text(item.get("source_url"), item.get("source_pdf_url")),
        "raw_text": optional_text(item.get("raw_text")),
        "parsed_at": first_text(item.get("parsed_at")),
        "is_synthetic": bool(item.get("is_synthetic", False)),
    }


def normalize_parse_log_item(
    provider_id: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    step = optional_text(item.get("step")) or "unknown"

    return {
        "provider_id": optional_text(item.get("provider_id")) or provider_id,
        "url": first_text(
            item.get("url"),
            item.get("source_url"),
            f"parser://{provider_id}/{step}",
        ),
        "parsed_at": first_text(
            item.get("parsed_at"),
            item.get("finished_at"),
            item.get("started_at"),
        ),
        "status": first_text(item.get("status"), "unknown"),
        "records_added": int(item.get("records_added") or 0),
        "error": item.get("error"),
    }


def is_user_task_template_log(item: dict[str, Any]) -> bool:
    text = " ".join(
        optional_text(value) or ""
        for value in (
            item.get("url"),
            item.get("source_url"),
            item.get("step"),
        )
    ).lower()

    return "user_task_templates" in text


def normalize_regions(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        value = [value]

    if not isinstance(value, list):
        return []

    regions = []

    for item in value:
        region = normalize_region(item)
        if region and region not in regions:
            regions.append(region)

    return regions


def normalize_region(value: Any) -> str | None:
    text = optional_text(value)
    if text is None:
        return None

    key = normalize_location_key(text)
    aliases = {
        "москва": "Moscow",
        "москве": "Moscow",
        "moscow": "Moscow",
        "ru moscow": "Moscow",
        "ru moscow 1": "Moscow",
        "ru-moscow": "Moscow",
        "ru-moscow-1": "Moscow",
        "санкт петербург": "Saint-Petersburg",
        "санкт петербурге": "Saint-Petersburg",
        "петербург": "Saint-Petersburg",
        "питер": "Saint-Petersburg",
        "saint petersburg": "Saint-Petersburg",
        "saint-petersburg": "Saint-Petersburg",
        "st petersburg": "Saint-Petersburg",
        "spb": "Saint-Petersburg",
        "новосибирск": "Novosibirsk",
        "новосибирске": "Novosibirsk",
        "novosibirsk": "Novosibirsk",
        "россия": "Russia",
        "россии": "Russia",
        "russia": "Russia",
    }

    if key in aliases:
        return aliases[key]

    return canonicalize_region(text) or text


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        value = [value]

    if not isinstance(value, list):
        return []

    result = []

    for item in value:
        text = optional_text(item)
        if text and text not in result:
            result.append(text)

    return result


def required_text(item: dict[str, Any], key: str) -> str:
    text = optional_text(item.get(key))
    if text is None:
        raise ValueError(f"Missing required field: {key}")
    return text


def first_text(*values: Any) -> str:
    for value in values:
        text = optional_text(value)
        if text:
            return text
    return ""


def optional_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


if __name__ == "__main__":
    main()
