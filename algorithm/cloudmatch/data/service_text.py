from algorithm.cloudmatch.schemas.service import Service


def build_service_text(service: Service) -> str:
    tech_tags = " ".join(service.tech_stack_tags)
    use_case_tags = " ".join(service.use_case_tags)
    compliance_tags = " ".join(service.compliance_tags)
    regions = " ".join(service.regions)

    parts = [
        service.name,
        service.name,
        service.name,
        service.category,
        service.category,
        tech_tags,
        tech_tags,
        tech_tags,
        use_case_tags,
        use_case_tags,
        use_case_tags,
        compliance_tags,
        regions,
        service.name,
        service.category,
        service.description,
        service.pricing_model or "",
        service.support_level or "",
    ]

    return " ".join(part for part in parts if part).lower()