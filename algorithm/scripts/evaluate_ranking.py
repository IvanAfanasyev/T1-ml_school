from algorithm.cloudmatch.agent.pipeline import SearchPipeline
from algorithm.cloudmatch.evaluation.golden_dataset import load_golden_dataset
from algorithm.cloudmatch.evaluation.metrics import (
    find_rank,
    mean_precision_at_3,
    mean_reciprocal_rank,
    precision_at_k,
    reciprocal_rank,
)
from algorithm.cloudmatch.schemas.evaluation import QueryEvaluationResult


def main() -> None:
    print("Loading golden dataset...")

    dataset = load_golden_dataset()

    print(f"Loaded queries: {len(dataset)}")

    print()
    print("Initializing search pipeline...")

    pipeline = SearchPipeline()

    evaluation_results: list[QueryEvaluationResult] = []

    print()
    print("Running evaluation...")

    for item in dataset:
        print()
        print("=" * 80)
        print(f"{item.query_id}: {item.query}")

        response = pipeline.search(
            user_query=item.query,
            with_explanation=False,
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

        print(f"Expected relevant: {item.relevant_service_ids}")
        print(f"Primary expected:  {item.primary_service_id}")
        print(f"Retrieved top-3:   {retrieved_ids}")
        print(f"Precision@3:      {p_at_3:.4f}")
        print(f"RR:               {rr:.4f}")
        print(f"First rel. rank:  {first_relevant_rank}")
        print(f"Primary rank:     {primary_rank}")

    print()
    print("=" * 80)
    print("Evaluation summary")
    print("=" * 80)

    mean_p3 = mean_precision_at_3(evaluation_results)
    mrr = mean_reciprocal_rank(evaluation_results)

    print(f"Queries evaluated: {len(evaluation_results)}")
    print(f"Mean Precision@3:  {mean_p3:.4f}")
    print(f"MRR:               {mrr:.4f}")


if __name__ == "__main__":
    main()