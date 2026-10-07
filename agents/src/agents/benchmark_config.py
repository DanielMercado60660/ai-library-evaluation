"""Pydantic models for v2.4 open-ended benchmark configuration and interactions."""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DomainWeights(BaseModel):
    """Distribution weights across service domains."""

    catalog: float = 0.3
    circulation: float = 0.5
    ill: float = 0.2


class ComplexityDistribution(BaseModel):
    """Distribution across complexity tiers."""

    simple: float = 0.5
    medium: float = 0.3
    complex: float = 0.2


class BenchmarkConfig(BaseModel):
    """Configuration for an open-ended benchmark session."""

    patron_pool: list[str] = Field(
        default_factory=lambda: [f"patron-{i:03d}" for i in range(1, 11)],
    )
    patron_category_filter: Optional[list[str]] = None
    interaction_count: int = Field(default=50, ge=1, le=2000)
    time_budget_seconds: int = Field(default=600, ge=30, le=7200)
    domain_weights: DomainWeights = Field(default_factory=DomainWeights)
    complexity_distribution: ComplexityDistribution = Field(
        default_factory=ComplexityDistribution
    )
    seed_before_run: bool = True
    stateful_sequences: bool = True
    random_seed: int = 42


class InteractionType(str, Enum):
    """All supported patron interaction types."""

    CATALOG_SEARCH = "catalog_search"
    BOOK_DETAIL = "book_detail"
    AVAILABILITY_CHECK = "availability_check"
    CHECKOUT = "checkout"
    HOLD = "hold"
    RETURN = "return"
    RENEWAL = "renewal"
    FINE_INQUIRY = "fine_inquiry"
    FINE_PAYMENT = "fine_payment"
    PATRON_SUMMARY = "patron_summary"
    ILL_REQUEST = "ill_request"
    ILL_STATUS = "ill_status"


INTERACTION_DOMAIN: dict[InteractionType, str] = {
    InteractionType.CATALOG_SEARCH: "catalog",
    InteractionType.BOOK_DETAIL: "catalog",
    InteractionType.AVAILABILITY_CHECK: "catalog",
    InteractionType.CHECKOUT: "circulation",
    InteractionType.HOLD: "circulation",
    InteractionType.RETURN: "circulation",
    InteractionType.RENEWAL: "circulation",
    InteractionType.FINE_INQUIRY: "circulation",
    InteractionType.FINE_PAYMENT: "circulation",
    InteractionType.PATRON_SUMMARY: "circulation",
    InteractionType.ILL_REQUEST: "ill",
    InteractionType.ILL_STATUS: "ill",
}

INTERACTION_COMPLEXITY: dict[InteractionType, str] = {
    InteractionType.CATALOG_SEARCH: "simple",
    InteractionType.BOOK_DETAIL: "simple",
    InteractionType.AVAILABILITY_CHECK: "simple",
    InteractionType.CHECKOUT: "medium",
    InteractionType.HOLD: "medium",
    InteractionType.RETURN: "medium",
    InteractionType.RENEWAL: "medium",
    InteractionType.FINE_INQUIRY: "medium",
    InteractionType.FINE_PAYMENT: "medium",
    InteractionType.PATRON_SUMMARY: "medium",
    InteractionType.ILL_REQUEST: "complex",
    InteractionType.ILL_STATUS: "complex",
}

TOOL_HINTS: dict[InteractionType, list[str]] = {
    InteractionType.CATALOG_SEARCH: ["search_books"],
    InteractionType.BOOK_DETAIL: ["get_book_details"],
    InteractionType.AVAILABILITY_CHECK: ["get_book_instances"],
    InteractionType.CHECKOUT: ["search_books", "checkout_item"],
    InteractionType.HOLD: ["place_hold"],
    InteractionType.RETURN: ["return_item"],
    InteractionType.RENEWAL: ["renew_checkout"],
    InteractionType.FINE_INQUIRY: ["get_patron_fines", "get_my_fines"],
    InteractionType.FINE_PAYMENT: ["pay_fine"],
    InteractionType.PATRON_SUMMARY: ["get_patron_summary", "get_my_patron_summary"],
    InteractionType.ILL_REQUEST: ["create_ill_request", "search_partner_catalog"],
    InteractionType.ILL_STATUS: ["list_my_ill_requests"],
}


class BenchmarkInteraction(BaseModel):
    """A single generated benchmark interaction."""

    interaction_id: str
    sequence_id: Optional[str] = None
    sequence_order: int = 0
    patron_id: str
    patron_name: str
    patron_category: str
    message: str
    interaction_type: InteractionType
    expected_domain: str
    expected_tool_hints: list[str] = Field(default_factory=list)
    complexity_tier: str
    is_edge_case: bool = False
    edge_case_type: Optional[str] = None


class InteractionResult(BaseModel):
    """Result of executing a single benchmark interaction."""

    interaction_id: str
    sequence_id: Optional[str] = None
    patron_id: str
    interaction_type: str
    expected_domain: str
    complexity_tier: str
    message_sent: str
    agent_response: str = ""
    tool_engaged: bool = False
    tool_calls_observed: list[str] = Field(default_factory=list)
    coherence_score: float = 0.0
    hallucination_detected: bool = False
    appropriate_refusal: bool = False
    is_edge_case: bool = False
    duration_ms: float = 0.0
    error: Optional[str] = None
    status: str = "completed"
