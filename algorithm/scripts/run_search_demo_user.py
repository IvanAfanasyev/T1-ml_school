from algorithm.cloudmatch.agent.pipeline import SearchPipeline
from algorithm.cloudmatch.agent.user_response_formatter import format_user_response
from algorithm.cloudmatch.data.repositories import DataRepository


def main() -> None:
    user_query = input("Введите запрос пользователя: ").strip()
    if not user_query:
        print("Запрос пустой.")
        return
    pipeline = SearchPipeline()
    data_repository = DataRepository()
    response = pipeline.search(user_query=user_query, with_explanation=True)
    print()
    print(format_user_response(response, data_repository))


if __name__ == "__main__":
    main()
