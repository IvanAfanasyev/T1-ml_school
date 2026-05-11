import json
from pathlib import Path

from algorithm.cloudmatch.agent.pipeline import SearchPipeline
from algorithm.cloudmatch.evaluation.golden_dataset import load_golden_dataset
from algorithm.cloudmatch.evaluation.llm_judge import LLMJudge
from algorithm.cloudmatch.evaluation.metrics import (
    find_rank,
    mean_precision_at_3,
    mean_reciprocal_rank,
    precision_at_k,
    reciprocal_rank,
)
from algorithm.cloudmatch.schemas.evaluation import QueryEvaluationResult
from algorithm.cloudmatch.schemas.ranking import SearchResponse


JUDGE_RESULTS_FILE = "data/evaluation/judge_results.json"


def main() -> None:
    print("Loading golden dataset...")

    dataset = load_golden_dataset()

    print(f"Loaded queries: {len(dataset)}")

    print()
    print("Initializing search pipeline and LLM judge...")

    pipeline = SearchPipeline()
    judge = LLMJudge()

    evaluation_results: list[QueryEvaluationResult] = []
    judge_results = []

    print()
    print("Running evaluation with LLM-as-a-judge...")

    for item in dataset:
        print()
        print("=" * 100)
        print(f"{item.query_id}: {item.query}")
        print("=" * 100)

        response = pipeline.search(
            user_query=item.query,
            with_explanation=True,
        )

        retrieved_ids = [
            result.service.service_id
            for result in response.results
        ]

        p_at_3 = precision_at_k(
            retrieved_ids=retrieved_ids,
            relevant_ids=item.relevant_service_ids,
            k=3,
        )

        rr, first_relevant_rank = reciprocal_rank(
            retrieved_ids=retrieved_ids,
            relevant_ids=item.relevant_service_ids,
        )

        primary_rank = find_rank(
            retrieved_ids=retrieved_ids,
            target_id=item.primary_service_id,
        )

        query_result = QueryEvaluationResult(
            query_id=item.query_id,
            query=item.query,
            expected_service_ids=item.relevant_service_ids,
            retrieved_service_ids=retrieved_ids,
            precision_at_3=p_at_3,
            reciprocal_rank=rr,
            first_relevant_rank=first_relevant_rank,
            primary_service_rank=primary_rank,
        )

        evaluation_results.append(query_result)

        print()
        print("=== Golden dataset labels ===")
        print(f"Expected relevant service_ids: {item.relevant_service_ids}")
        print(f"Primary expected service_id:  {item.primary_service_id}")
        print(f"Notes: {item.notes}")

        print_full_system_answer(response)

        print()
        print("=== Automatic metrics ===")
        print(f"Retrieved top-3 service_ids: {retrieved_ids}")
        print(f"Precision@3:                {p_at_3:.4f}")
        print(f"RR:                         {rr:.4f}")
        print(f"First relevant rank:        {first_relevant_rank}")
        print(f"Primary service rank:       {primary_rank}")

        judge_result = judge.judge(
            golden_item=item,
            response=response,
            precision_at_3=p_at_3,
            reciprocal_rank=rr,
        )

        judge_results.append(
            {
                "query_id": item.query_id,
                "query": item.query,
                "expected_service_ids": item.relevant_service_ids,
                "primary_service_id": item.primary_service_id,
                "retrieved_service_ids": retrieved_ids,
                "precision_at_3": p_at_3,
                "reciprocal_rank": rr,
                "first_relevant_rank": first_relevant_rank,
                "primary_service_rank": primary_rank,
                "system_summary": response.summary,
                "system_top_3": [
                    build_result_dump(result)
                    for result in response.results
                ],
                "judge": judge_result,
            }
        )

        print_judge_result(judge_result)

    print()
    print("=" * 100)
    print("Evaluation summary")
    print("=" * 100)

    mean_p3 = mean_precision_at_3(evaluation_results)
    mrr = mean_reciprocal_rank(evaluation_results)

    mean_judge_overall = average_judge_score(
        judge_results=judge_results,
        field="overall_score",
    )

    mean_judge_relevance = average_judge_score(
        judge_results=judge_results,
        field="relevance_score",
    )

    mean_judge_faithfulness = average_judge_score(
        judge_results=judge_results,
        field="explanation_faithfulness_score",
    )

    verdict_counts = count_verdicts(judge_results)

    print(f"Queries evaluated:             {len(evaluation_results)}")
    print(f"Mean Precision@3:              {mean_p3:.4f}")
    print(f"MRR:                           {mrr:.4f}")
    print(f"Mean Judge Overall Score:      {mean_judge_overall:.4f}")
    print(f"Mean Judge Relevance Score:    {mean_judge_relevance:.4f}")
    print(f"Mean Judge Faithfulness Score: {mean_judge_faithfulness:.4f}")
    print(f"Judge Verdicts:                {verdict_counts}")

    save_judge_results(judge_results)


def print_full_system_answer(response: SearchResponse) -> None:
    """
    Печатает полный ответ системы до LLM-as-a-judge.

    Это нужно, чтобы видеть:
    - как система поняла запрос;
    - какой top-3 она выдала;
    - какие тарифы подтянула;
    - какие совпадения и несовпадения нашла;
    - какое explanation получила пользовательская часть.
    """

    print()
    print("=== Structured query ===")
    print(f"task_category: {response.structured_query.get('task_category')}")
    print(f"intent:        {response.structured_query.get('intent')}")
    print(f"tech_stack:    {response.structured_query.get('tech_stack')}")
    print(f"use_case:      {response.structured_query.get('use_case')}")
    print(f"requirements:  {response.structured_query.get('requirements')}")

    constraints = response.structured_query.get("constraints", {})
    print(f"region:        {constraints.get('region')}")
    print(f"effective:     {constraints.get('effective_region')}")
    print(f"fallback:      {constraints.get('region_fallback_used')}")
    print(f"budget_max:    {constraints.get('budget_max')}")

    print()
    print("=== System summary ===")
    print(response.summary)

    print()
    print("=== System top-3 answer ===")

    for result in response.results:
        service = result.service
        scores = result.score_breakdown
        matched = result.matched_entities

        print()
        print("-" * 100)
        print(f"{result.rank}. {service.name}")
        print("-" * 100)

        print(f"service_id:       {service.service_id}")
        print(f"provider_id:      {service.provider_id}")
        print(f"category:         {service.category}")
        print(f"description:      {service.description}")
        print(f"support_level:    {service.support_level}")
        print(f"pricing_model:    {service.pricing_model}")
        print(f"price_from:       {result.price_summary.price_from_rub} {result.price_summary.price_unit}")
        print(f"price_source:     {result.price_summary.source}")

        print()
        print("Scores:")
        print(f"  embedding_score:      {scores.embedding_score:.4f}")
        print(f"  bm25_score:           {scores.bm25_score:.4f}")
        print(f"  retrieval_score:      {scores.retrieval_score:.4f}")
        print(f"  entity_match_score:   {scores.entity_match_score:.4f}")
        print(f"  final_score:          {scores.final_score:.4f}")

        print()
        print("Matched / missing entities:")
        print(f"  matched_tech_stack:    {matched.matched_tech_stack}")
        print(f"  missing_tech_stack:    {matched.missing_tech_stack}")
        print(f"  matched_use_case:      {matched.matched_use_case}")
        print(f"  missing_use_case:      {matched.missing_use_case}")
        print(f"  matched_components:    {matched.matched_components}")
        print(f"  missing_components:    {matched.missing_components}")
        print(f"  requirements_score:    {matched.requirements_score:.4f}")
        print(f"  matched_requirements:  {matched.matched_requirements}")
        print(f"  missing_requirements:  {matched.missing_requirements}")
        print(f"  budget_status:         {matched.budget_status}")
        print(f"  budget_score:          {matched.budget_score:.4f}")
        print(f"  matched_region:        {matched.matched_region}")

        print()
        print("Selected pricing items:")

        if not result.selected_pricing_items:
            print("  Нет выбранных тарифных позиций.")
        else:
            for item in result.selected_pricing_items:
                print(
                    f"  - {item.item_name}: "
                    f"{item.price_rub} {item.price_unit} "
                    f"| item_type={item.item_type} "
                    f"| billing_period={item.billing_period} "
                    f"| region={item.region} "
                    f"| tags={item.configuration_tags}"
                )

        print()
        print("Explanation:")
        print(result.explanation)


def print_judge_result(judge_result: dict) -> None:
    """
    Печатает оценку LLM-as-a-judge после полного ответа системы.
    """

    print()
    print("=== LLM-as-a-judge evaluation ===")
    print(f"verdict:                         {judge_result['verdict']}")
    print(f"relevance_score:                 {judge_result['relevance_score']:.4f}")
    print(f"ranking_order_score:             {judge_result['ranking_order_score']:.4f}")
    print(f"explanation_faithfulness_score:  {judge_result['explanation_faithfulness_score']:.4f}")
    print(f"missing_req_handling_score:      {judge_result['missing_requirements_handling_score']:.4f}")
    print(f"usefulness_score:                {judge_result['usefulness_score']:.4f}")
    print(f"overall_score:                   {judge_result['overall_score']:.4f}")
    print(f"  judge_source:                    {judge_result.get('judge_source', 'unknown')}")
    print(f"  judge_attempts:                  {judge_result.get('judge_attempts', 'unknown')}")

    if judge_result["strengths"]:
        print()
        print("Strengths:")
        for strength in judge_result["strengths"]:
            print(f"  - {strength}")

    if judge_result["issues"]:
        print()
        print("Issues:")
        for issue in judge_result["issues"]:
            print(f"  - {issue}")

    if judge_result["recommendations"]:
        print()
        print("Recommendations:")
        for recommendation in judge_result["recommendations"]:
            print(f"  - {recommendation}")


def build_result_dump(result) -> dict:
    """
    Сохраняет полный top-3 результат в judge_results.json.
    """

    service = result.service
    scores = result.score_breakdown
    matched = result.matched_entities

    return {
        "rank": result.rank,
        "service_id": service.service_id,
        "provider_id": service.provider_id,
        "service_name": service.name,
        "category": service.category,
        "description": service.description,
        "support_level": service.support_level,
        "pricing_model": service.pricing_model,
        "price_summary": result.price_summary.model_dump(),
        "score_breakdown": {
            "embedding_score": scores.embedding_score,
            "bm25_score": scores.bm25_score,
            "retrieval_score": scores.retrieval_score,
            "entity_match_score": scores.entity_match_score,
            "final_score": scores.final_score,
        },
        "matched_entities": {
            "matched_tech_stack": matched.matched_tech_stack,
            "missing_tech_stack": matched.missing_tech_stack,
            "matched_use_case": matched.matched_use_case,
            "missing_use_case": matched.missing_use_case,
            "matched_components": matched.matched_components,
            "missing_components": matched.missing_components,
            "matched_requirements": matched.matched_requirements,
            "missing_requirements": matched.missing_requirements,
            "requirements_score": matched.requirements_score,
            "budget_status": matched.budget_status,
            "budget_score": matched.budget_score,
            "matched_region": matched.matched_region,
        },
        "selected_pricing_items": [
            item.model_dump()
            for item in result.selected_pricing_items
        ],
        "explanation": result.explanation,
    }


def average_judge_score(
    judge_results: list[dict],
    field: str,
) -> float:
    if not judge_results:
        return 0.0

    scores = [
        item["judge"].get(field, 0.0)
        for item in judge_results
    ]

    return sum(scores) / len(scores)


def count_verdicts(judge_results: list[dict]) -> dict[str, int]:
    counts = {
        "pass": 0,
        "warn": 0,
        "fail": 0,
    }

    for item in judge_results:
        verdict = item["judge"].get("verdict", "warn")

        if verdict not in counts:
            verdict = "warn"

        counts[verdict] += 1

    return counts


def save_judge_results(judge_results: list[dict]) -> None:
    output_path = Path(JUDGE_RESULTS_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            judge_results,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(f"Judge results saved to: {output_path}")


if __name__ == "__main__":
    main()
