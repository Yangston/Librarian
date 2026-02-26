"""Unit tests for Phase 2 entity resolution."""

import unittest

from app.entity_resolution.resolver import EntityResolver
from app.extraction.types import ExtractedEntity


class EntityResolverTests(unittest.TestCase):
    def test_aliases_merge_to_canonical_company_name(self) -> None:
        resolver = EntityResolver()
        entities = [
            ExtractedEntity(
                name="AAPL",
                entity_type="Company",
                aliases=["Apple", "Apple Inc."],
            ),
            ExtractedEntity(
                name="Apple Inc.",
                entity_type="Company",
                aliases=["Apple", "AAPL"],
            ),
            ExtractedEntity(
                name="Apple",
                entity_type="Company",
                aliases=["AAPL"],
            ),
            ExtractedEntity(
                name="Microsoft",
                entity_type="Company",
                aliases=["MSFT"],
            ),
        ]

        plan = resolver.resolve(entities)

        assignments = plan.assignments
        self.assertEqual(len(assignments), 4)
        self.assertEqual(assignments[0].canonical_name, "Apple Inc.")
        self.assertEqual(assignments[1].canonical_name, "Apple Inc.")
        self.assertEqual(assignments[2].canonical_name, "Apple Inc.")
        self.assertEqual(assignments[3].canonical_name, "Microsoft")

        apple_cluster_indexes = {assignments[i].canonical_cluster_index for i in (0, 1, 2)}
        self.assertEqual(len(apple_cluster_indexes), 1)
        self.assertEqual(assignments[3].merged, False)
        self.assertEqual(sum(1 for assignment in assignments if assignment.merged), 2)

        apple_cluster_index = assignments[1].canonical_cluster_index
        self.assertEqual(plan.resolve_reference("AAPL", "Company"), apple_cluster_index)
        self.assertEqual(plan.resolve_reference("Apple", "Company"), apple_cluster_index)
        self.assertEqual(plan.resolve_reference("Apple Inc.", "Company"), apple_cluster_index)

    def test_same_name_different_types_do_not_merge(self) -> None:
        resolver = EntityResolver()
        entities = [
            ExtractedEntity(name="Apple", entity_type="Company"),
            ExtractedEntity(name="Apple", entity_type="Concept"),
        ]

        plan = resolver.resolve(entities)

        self.assertEqual(len(plan.assignments), 2)
        self.assertNotEqual(
            plan.assignments[0].canonical_cluster_index,
            plan.assignments[1].canonical_cluster_index,
        )
        self.assertFalse(plan.assignments[0].merged)
        self.assertFalse(plan.assignments[1].merged)


if __name__ == "__main__":
    unittest.main()
