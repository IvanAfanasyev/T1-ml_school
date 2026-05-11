import unittest

from algorithm.cloudmatch.geo.region_resolver import (
    extract_region_from_text,
    match_available_region,
    resolve_nearby_available_regions,
)


class RegionResolverTest(unittest.TestCase):
    def test_extracts_belgorod_from_inflected_russian_text(self) -> None:
        self.assertEqual(
            extract_region_from_text("нужна база данных в Белгороде"),
            "Belgorod",
        )

    def test_matches_saint_petersburg_alias_to_available_region(self) -> None:
        self.assertEqual(
            match_available_region(
                requested_region="в питере",
                available_regions=["Moscow", "Russia", "Saint-Petersburg"],
            ),
            "Saint-Petersburg",
        )

    def test_resolves_belgorod_to_nearest_available_regions(self) -> None:
        self.assertEqual(
            resolve_nearby_available_regions(
                requested_region="Belgorod",
                available_regions=["Moscow", "Russia", "Saint-Petersburg"],
            ),
            ["Moscow", "Saint-Petersburg", "Russia"],
        )


if __name__ == "__main__":
    unittest.main()
