"""Unit tests for controlled entity type normalization."""

import unittest

from app.schema.entity_types import ENTITY_TYPE_VALUES, normalize_entity_type


class EntityTypeNormalizationTests(unittest.TestCase):
    def test_location_type_is_supported(self) -> None:
        self.assertIn("Location", ENTITY_TYPE_VALUES)
        self.assertEqual(normalize_entity_type("location"), "Location")
        self.assertEqual(normalize_entity_type("city"), "Location")
        self.assertEqual(normalize_entity_type("Region"), "Location")

    def test_unknown_type_falls_back_to_other(self) -> None:
        self.assertEqual(normalize_entity_type("AssetClass"), "Other")
        self.assertEqual(normalize_entity_type(None), "Other")


if __name__ == "__main__":
    unittest.main()
