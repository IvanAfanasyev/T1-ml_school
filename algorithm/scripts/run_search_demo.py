from algorithm.cloudmatch.agent.pipeline import SearchPipeline


def main() -> None:
    user_query = input("Введите запрос пользователя: ").strip()

    if not user_query:
        print("Запрос пустой.")
        return

    pipeline = SearchPipeline()
    response = pipeline.search(
        user_query=user_query,
        with_explanation=True,
    )

    print()
    print("=== Structured query ===")
    print(f"task_category: {response.structured_query.get('task_category')}")
    print(f"intent: {response.structured_query.get('intent')}")
    print(f"tech_stack: {response.structured_query.get('tech_stack')}")
    print(f"use_case: {response.structured_query.get('use_case')}")
    print(f"requirements: {response.structured_query.get('requirements')}")
    print(f"region: {response.structured_query.get('constraints', {}).get('region')}")
    print(f"effective_region: {response.structured_query.get('constraints', {}).get('effective_region')}")
    print(f"region_fallback_used: {response.structured_query.get('constraints', {}).get('region_fallback_used')}")
    print(f"nearby_regions: {response.structured_query.get('constraints', {}).get('nearby_regions')}")
    print(f"budget_max: {response.structured_query.get('constraints', {}).get('budget_max')}")

    print()
    print("=== Summary ===")
    print(response.summary)

    print()
    print("=== Top-3 recommendations ===")

    for result in response.results:
        service = result.service
        scores = result.score_breakdown
        matched = result.matched_entities

        print()
        print(f"{result.rank}. {service.name}")
        print(f"   provider_id: {service.provider_id}")
        print(f"   category: {service.category}")
        print(f"   support_level: {service.support_level}")
        print(f"   pricing_model: {service.pricing_model}")
        print(f"   price_from: {result.price_summary.price_from_rub} {result.price_summary.price_unit}")
        print(f"   budget_status: {matched.budget_status}")
        print(f"   retrieval_score: {scores.retrieval_score:.4f}")
        print(f"   entity_match_score: {scores.entity_match_score:.4f}")
        print(f"   final_score: {scores.final_score:.4f}")

        print(f"   matched_tech_stack: {matched.matched_tech_stack}")
        print(f"   missing_tech_stack: {matched.missing_tech_stack}")
        print(f"   matched_components: {matched.matched_components}")
        print(f"   missing_components: {matched.missing_components}")
        print(f"   requirements_score: {matched.requirements_score:.4f}")
        print(f"   matched_requirements: {matched.matched_requirements}")
        print(f"   missing_requirements: {matched.missing_requirements}")

        if result.selected_pricing_items:
            print("   pricing_items:")

            for item in result.selected_pricing_items:
                print(
                    f"   - {item.item_name}: "
                    f"{item.price_rub} {item.price_unit} "
                    f"({item.item_type}, billing_period={item.billing_period})"
                )

        print()
        print("   explanation:")
        print(f"   {result.explanation}")


if __name__ == "__main__":
    main()
