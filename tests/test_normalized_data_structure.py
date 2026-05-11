import json
import unittest
from pathlib import Path

from algorithm.cloudmatch.data.pricing_repository import PricingRepository
from algorithm.cloudmatch.data.repositories import DataRepository


NORMALIZED_DIR = Path("data/normalized")


class NormalizedDataStructureTest(unittest.TestCase):
    def test_runtime_dataset_uses_final_json_structure(self) -> None:
        expected_files = {
            "providers.json",
            "services.json",
            "service_pricing_items.json",
            "parse_log.json",
            "errors.json",
        }

        actual_files = {
            path.name
            for path in NORMALIZED_DIR.iterdir()
            if path.is_file() and path.suffix == ".json"
        }

        self.assertEqual(actual_files, expected_files)
        self.assertFalse((NORMALIZED_DIR / "user_task_templates.json").exists())
        self.assertFalse((NORMALIZED_DIR / "providers").exists())
        self.assertFalse((NORMALIZED_DIR / "services").exists())

    def test_services_and_pricing_items_load_into_project_schemas(self) -> None:
        data_repository = DataRepository()
        pricing_repository = PricingRepository()

        self.assertGreater(len(data_repository.providers), 0)
        self.assertGreater(len(data_repository.services), 0)
        self.assertGreater(len(pricing_repository.pricing_items), 0)

        service_ids = {
            service.service_id
            for service in data_repository.services
        }
        pricing_service_ids = {
            item.service_id
            for item in pricing_repository.pricing_items
        }

        self.assertTrue(pricing_service_ids.issubset(service_ids))

    def test_parse_log_has_common_shape(self) -> None:
        parse_log = json.loads(
            (NORMALIZED_DIR / "parse_log.json").read_text(encoding="utf-8")
        )

        self.assertGreater(len(parse_log), 0)

        required_keys = {
            "provider_id",
            "url",
            "parsed_at",
            "status",
            "records_added",
            "error",
        }

        for item in parse_log:
            self.assertEqual(set(item), required_keys)


if __name__ == "__main__":
    unittest.main()
