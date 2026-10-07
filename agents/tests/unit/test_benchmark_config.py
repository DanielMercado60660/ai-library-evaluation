"""Unit tests for benchmark_config models."""

import pytest

from agents.benchmark_config import (
    BenchmarkConfig,
    BenchmarkInteraction,
    ComplexityDistribution,
    DomainWeights,
    INTERACTION_COMPLEXITY,
    INTERACTION_DOMAIN,
    InteractionResult,
    InteractionType,
    TOOL_HINTS,
)


class TestDomainWeights:
    """Validate DomainWeights defaults and constraints."""

    def test_defaults(self):
        dw = DomainWeights()
        assert dw.catalog == 0.3
        assert dw.circulation == 0.5
        assert dw.ill == 0.2

    def test_custom_values(self):
        dw = DomainWeights(catalog=0.5, circulation=0.3, ill=0.2)
        assert dw.catalog == 0.5


class TestComplexityDistribution:
    """Validate ComplexityDistribution defaults."""

    def test_defaults(self):
        cd = ComplexityDistribution()
        assert cd.simple == 0.5
        assert cd.medium == 0.3
        assert cd.complex == 0.2


class TestBenchmarkConfig:
    """Validate BenchmarkConfig defaults, validation, and patron filtering."""

    def test_defaults(self):
        config = BenchmarkConfig()
        assert config.interaction_count == 50
        assert config.time_budget_seconds == 600
        assert config.random_seed == 42
        assert config.seed_before_run is True
        assert config.stateful_sequences is True
        assert len(config.patron_pool) == 10

    def test_patron_pool_default_ids(self):
        config = BenchmarkConfig()
        assert config.patron_pool[0] == "patron-001"
        assert config.patron_pool[9] == "patron-010"

    def test_interaction_count_bounds(self):
        config = BenchmarkConfig(interaction_count=1)
        assert config.interaction_count == 1

        config = BenchmarkConfig(interaction_count=2000)
        assert config.interaction_count == 2000

    def test_interaction_count_below_min_fails(self):
        with pytest.raises(Exception):
            BenchmarkConfig(interaction_count=0)

    def test_interaction_count_above_max_fails(self):
        with pytest.raises(Exception):
            BenchmarkConfig(interaction_count=2001)

    def test_time_budget_bounds(self):
        config = BenchmarkConfig(time_budget_seconds=30)
        assert config.time_budget_seconds == 30

        config = BenchmarkConfig(time_budget_seconds=7200)
        assert config.time_budget_seconds == 7200

    def test_patron_category_filter(self):
        config = BenchmarkConfig(patron_category_filter=["adult", "senior"])
        assert config.patron_category_filter == ["adult", "senior"]

    def test_no_patron_category_filter(self):
        config = BenchmarkConfig()
        assert config.patron_category_filter is None

    def test_model_validate_dict(self):
        """API passes raw dict — ensure model_validate works."""
        raw = {"interaction_count": 10, "random_seed": 99}
        config = BenchmarkConfig.model_validate(raw)
        assert config.interaction_count == 10
        assert config.random_seed == 99


class TestInteractionType:
    """Validate InteractionType enum and domain/complexity/tool mappings."""

    def test_all_types_have_domain_mapping(self):
        for itype in InteractionType:
            assert itype in INTERACTION_DOMAIN, f"{itype} missing from INTERACTION_DOMAIN"

    def test_all_types_have_complexity_mapping(self):
        for itype in InteractionType:
            assert itype in INTERACTION_COMPLEXITY, f"{itype} missing from INTERACTION_COMPLEXITY"

    def test_all_types_have_tool_hints(self):
        for itype in InteractionType:
            assert itype in TOOL_HINTS, f"{itype} missing from TOOL_HINTS"

    def test_twelve_types(self):
        assert len(InteractionType) == 12

    def test_catalog_domain_types(self):
        catalog_types = [t for t, d in INTERACTION_DOMAIN.items() if d == "catalog"]
        assert InteractionType.CATALOG_SEARCH in catalog_types
        assert InteractionType.BOOK_DETAIL in catalog_types
        assert InteractionType.AVAILABILITY_CHECK in catalog_types

    def test_circulation_domain_types(self):
        circ_types = [t for t, d in INTERACTION_DOMAIN.items() if d == "circulation"]
        assert InteractionType.CHECKOUT in circ_types
        assert InteractionType.HOLD in circ_types

    def test_ill_domain_types(self):
        ill_types = [t for t, d in INTERACTION_DOMAIN.items() if d == "ill"]
        assert InteractionType.ILL_REQUEST in ill_types
        assert InteractionType.ILL_STATUS in ill_types


class TestBenchmarkInteraction:
    """Validate BenchmarkInteraction model."""

    def test_basic_construction(self):
        ix = BenchmarkInteraction(
            interaction_id="bm-0001",
            patron_id="patron-001",
            patron_name="Tusker Ivory",
            patron_category="adult",
            message="Find me a book",
            interaction_type=InteractionType.CATALOG_SEARCH,
            expected_domain="catalog",
            complexity_tier="simple",
        )
        assert ix.interaction_id == "bm-0001"
        assert ix.is_edge_case is False
        assert ix.sequence_id is None
        assert ix.sequence_order == 0

    def test_edge_case_flag(self):
        ix = BenchmarkInteraction(
            interaction_id="bm-0002",
            patron_id="patron-002",
            patron_name="Patron",
            patron_category="adult",
            message="Checkout blocked?",
            interaction_type=InteractionType.CHECKOUT,
            expected_domain="circulation",
            complexity_tier="medium",
            is_edge_case=True,
            edge_case_type="blocked_patron_checkout",
        )
        assert ix.is_edge_case is True
        assert ix.edge_case_type == "blocked_patron_checkout"


class TestInteractionResult:
    """Validate InteractionResult model."""

    def test_defaults(self):
        result = InteractionResult(
            interaction_id="bm-0001",
            patron_id="patron-001",
            interaction_type="catalog_search",
            expected_domain="catalog",
            complexity_tier="simple",
            message_sent="Find me a book",
        )
        assert result.status == "completed"
        assert result.tool_engaged is False
        assert result.coherence_score == 0.0
        assert result.hallucination_detected is False
        assert result.error is None
