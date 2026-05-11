import unittest

from algorithm.cloudmatch.agent.query_extractor import QueryExtractor


class QueryExtractorNormalizationTest(unittest.TestCase):
    def test_llm_request_type_is_preserved_for_bundle(self) -> None:
        extractor = QueryExtractor.__new__(QueryExtractor)

        normalized = extractor._normalize_llm_json(
            data={
                "request_type": "solution_bundle",
                "required_components": [
                    {"component": "compute"},
                    {"component": "managed_database", "db_engine": "postgresql"},
                ],
            },
            user_query="backend и база",
        )

        self.assertEqual(normalized["request_type"], "solution_bundle")

    def test_request_type_falls_back_to_components(self) -> None:
        extractor = QueryExtractor.__new__(QueryExtractor)

        normalized = extractor._normalize_llm_json(
            data={
                "required_components": [
                    {"component": "compute"},
                    {"component": "object_storage"},
                ],
            },
            user_query="backend и картинки",
        )

        self.assertEqual(normalized["request_type"], "solution_bundle")

    def test_russian_database_aliases_are_normalized(self) -> None:
        extractor = QueryExtractor.__new__(QueryExtractor)

        normalized = extractor._normalize_llm_json(
            data={
                "request_type": "single_service",
                "tech_stack": ["посгрискл", "майскл"],
                "required_components": [
                    {"component": "managed_database", "db_engine": "мускул"}
                ],
            },
            user_query="посгрискл или майскл",
        )

        self.assertEqual(normalized["tech_stack"], ["postgresql", "mysql"])
        self.assertEqual(
            normalized["required_components"][0]["db_engine"],
            "mysql",
        )


if __name__ == "__main__":
    unittest.main()
