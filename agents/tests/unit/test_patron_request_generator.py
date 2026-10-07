"""Unit tests for PatronRequestGenerator."""

from collections import Counter

import pytest

from agents.benchmark_config import (
    BenchmarkConfig,
    BenchmarkInteraction,
    INTERACTION_DOMAIN,
    InteractionType,
)
from agents.patron_request_generator import PatronRequestGenerator


@pytest.fixture
def default_config() -> BenchmarkConfig:
    return BenchmarkConfig(interaction_count=50, random_seed=42)


@pytest.fixture
def small_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        interaction_count=10,
        random_seed=99,
        stateful_sequences=False,
    )


class TestDeterminism:
    """Same seed must produce identical output."""

    def test_same_seed_same_output(self, default_config):
        gen1 = PatronRequestGenerator(default_config)
        gen2 = PatronRequestGenerator(default_config)

        results1 = gen1.generate()
        results2 = gen2.generate()

        assert len(results1) == len(results2)
        for a, b in zip(results1, results2):
            assert a.interaction_id == b.interaction_id
            assert a.message == b.message
            assert a.patron_id == b.patron_id
            assert a.interaction_type == b.interaction_type

    def test_different_seed_different_output(self):
        config1 = BenchmarkConfig(interaction_count=20, random_seed=42)
        config2 = BenchmarkConfig(interaction_count=20, random_seed=99)

        results1 = PatronRequestGenerator(config1).generate()
        results2 = PatronRequestGenerator(config2).generate()

        # Should be same length but different content
        assert len(results1) == len(results2)
        messages1 = [r.message for r in results1]
        messages2 = [r.message for r in results2]
        assert messages1 != messages2


class TestInteractionCount:
    """Validate exact count and basic structure."""

    def test_exact_count(self, default_config):
        results = PatronRequestGenerator(default_config).generate()
        assert len(results) == 50

    def test_small_count(self, small_config):
        results = PatronRequestGenerator(small_config).generate()
        assert len(results) == 10

    def test_single_interaction(self):
        config = BenchmarkConfig(interaction_count=1, random_seed=1, stateful_sequences=False)
        results = PatronRequestGenerator(config).generate()
        assert len(results) == 1

    def test_large_count(self):
        config = BenchmarkConfig(interaction_count=200, random_seed=42)
        results = PatronRequestGenerator(config).generate()
        assert len(results) == 200


class TestInteractionStructure:
    """Validate interaction fields are populated correctly."""

    def test_all_interactions_have_required_fields(self, default_config):
        results = PatronRequestGenerator(default_config).generate()
        for ix in results:
            assert ix.interaction_id
            assert ix.patron_id
            assert ix.message
            assert ix.interaction_type in InteractionType
            assert ix.expected_domain in ("catalog", "circulation", "ill")
            assert ix.complexity_tier in ("simple", "medium", "complex")

    def test_unique_interaction_ids(self, default_config):
        results = PatronRequestGenerator(default_config).generate()
        ids = [ix.interaction_id for ix in results]
        assert len(ids) == len(set(ids))

    def test_messages_reference_seed_data(self, default_config):
        """Messages should contain real book titles or domain keywords, not placeholders."""
        results = PatronRequestGenerator(default_config).generate()
        placeholder_count = sum(
            1 for ix in results
            if "{book_title}" in ix.message or "{author}" in ix.message
        )
        assert placeholder_count == 0, "Unfilled template placeholders found"


class TestDomainDistribution:
    """Validate domain distribution roughly matches weights."""

    def test_domain_distribution_within_tolerance(self):
        config = BenchmarkConfig(interaction_count=200, random_seed=42, stateful_sequences=False)
        results = PatronRequestGenerator(config).generate()

        domain_counts = Counter(ix.expected_domain for ix in results)
        total = len(results)

        # Default weights: catalog=0.3, circulation=0.5, ill=0.2
        # With 200 samples, allow 15% tolerance
        catalog_pct = domain_counts["catalog"] / total
        circ_pct = domain_counts["circulation"] / total
        ill_pct = domain_counts["ill"] / total

        assert 0.10 < catalog_pct < 0.55, f"catalog: {catalog_pct:.2f}"
        assert 0.25 < circ_pct < 0.75, f"circulation: {circ_pct:.2f}"
        assert 0.05 < ill_pct < 0.40, f"ill: {ill_pct:.2f}"

    def test_all_domains_present(self, default_config):
        results = PatronRequestGenerator(default_config).generate()
        domains = set(ix.expected_domain for ix in results)
        assert "catalog" in domains
        assert "circulation" in domains
        assert "ill" in domains


class TestStatefulSequences:
    """Validate stateful sequence generation."""

    def test_sequences_share_sequence_id(self, default_config):
        results = PatronRequestGenerator(default_config).generate()
        seq_ids = [ix.sequence_id for ix in results if ix.sequence_id is not None]
        assert len(seq_ids) > 0, "No stateful sequences generated"

        # Group by sequence_id
        from collections import defaultdict
        groups = defaultdict(list)
        for ix in results:
            if ix.sequence_id:
                groups[ix.sequence_id].append(ix)

        for seq_id, group in groups.items():
            assert len(group) >= 2, f"Sequence {seq_id} has only {len(group)} steps"

    def test_no_sequences_when_disabled(self):
        config = BenchmarkConfig(interaction_count=30, random_seed=42, stateful_sequences=False)
        results = PatronRequestGenerator(config).generate()
        seq_count = sum(1 for ix in results if ix.sequence_id is not None)
        assert seq_count == 0

    def test_sequences_share_same_patron(self, default_config):
        results = PatronRequestGenerator(default_config).generate()
        from collections import defaultdict
        groups = defaultdict(list)
        for ix in results:
            if ix.sequence_id:
                groups[ix.sequence_id].append(ix)

        for seq_id, group in groups.items():
            patron_ids = set(ix.patron_id for ix in group)
            assert len(patron_ids) == 1, f"Sequence {seq_id} has multiple patrons: {patron_ids}"


class TestEdgeCases:
    """Validate edge case generation."""

    def test_edge_cases_present(self, default_config):
        results = PatronRequestGenerator(default_config).generate()
        edge_cases = [ix for ix in results if ix.is_edge_case]
        assert len(edge_cases) > 0, "No edge cases generated"

    def test_edge_cases_have_type(self, default_config):
        results = PatronRequestGenerator(default_config).generate()
        for ix in results:
            if ix.is_edge_case:
                assert ix.edge_case_type is not None
                assert ix.edge_case_type in (
                    "blocked_patron_checkout",
                    "at_limit_checkout",
                    "duplicate_hold",
                    "overdue_fine_inquiry",
                )

    def test_no_edge_cases_when_count_too_small(self):
        config = BenchmarkConfig(interaction_count=2, random_seed=42, stateful_sequences=False)
        results = PatronRequestGenerator(config).generate()
        # With count=2, 10% edge budget = 0
        edge_count = sum(1 for ix in results if ix.is_edge_case)
        assert edge_count == 0
