from algorithm.cloudmatch.schemas.service import Service


def build_service_text(service: Service) -> str:
    parts = [
        service.name,
        service.category,
        service.description,
        " ".join(service.tech_stack_tags),
        " ".join(service.use_case_tags),
        " ".join(service.compliance_tags),
        " ".join(service.regions),
        service.pricing_model or "",
        service.support_level or "",
    ]

    return " ".join(part for part in parts if part).lower()