"""Template-based deterministic patron request generator for v2.4 benchmark.

Loads seed data from the ``data/`` directory and generates
:class:`BenchmarkInteraction` objects using string templates and
weighted random sampling. Uses ``random.Random(seed)`` for full
reproducibility.
"""

import json
import random as random_module
from pathlib import Path
from typing import Any

from agents.benchmark_config import (
    BenchmarkConfig,
    BenchmarkInteraction,
    InteractionType,
    INTERACTION_COMPLEXITY,
    INTERACTION_DOMAIN,
    TOOL_HINTS,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CATALOG_PATH = _REPO_ROOT / "data" / "hanno_memorial_library_catalog.json"
_PATRONS_PATH = _REPO_ROOT / "data" / "hanno_patrons.json"

PARTNER_LIBRARIES = [
    ("mastodon-institute", "Mastodon Institute"),
    ("mammoth-valley", "Mammoth Valley Library"),
    ("ivory-tower", "Ivory Tower Collection"),
    ("tusk-archive", "Tusk Archive"),
]

# ---------------------------------------------------------------------------
# Message templates per interaction type
# ---------------------------------------------------------------------------

CATALOG_SEARCH_TEMPLATES = [
    "Can you help me find books by {author}?",
    "I'm looking for books in the {genre} genre. What do you have?",
    "Do you have anything by {author} in stock?",
    "Search for '{book_title}' please.",
    "I'd like to find books in stratum {stratum}.",
    "What {genre} books do you carry?",
]

BOOK_DETAIL_TEMPLATES = [
    "Can you tell me more about '{book_title}'?",
    "What are the details on '{book_title}' by {author}?",
    "I need information about ISBN {isbn}.",
    "Tell me about '{book_title}' — who wrote it and when?",
]

AVAILABILITY_TEMPLATES = [
    "Is '{book_title}' available right now?",
    "Do you have any copies of '{book_title}' on the shelf?",
    "Check availability for '{book_title}' by {author}.",
]

CHECKOUT_TEMPLATES = [
    "I'd like to check out '{book_title}'.",
    "Can I borrow '{book_title}' by {author}?",
    "Please check out '{book_title}' for me.",
]

HOLD_TEMPLATES = [
    "Can you place a hold on '{book_title}' for me?",
    "I'd like to reserve '{book_title}'.",
    "Put a hold on '{book_title}' please.",
]

RETURN_TEMPLATES = [
    "I'd like to return '{book_title}'.",
    "I'm returning '{book_title}'.",
    "Please process a return for '{book_title}'.",
]

RENEWAL_TEMPLATES = [
    "Can I renew my checkout of '{book_title}'?",
    "I'd like to extend my loan for '{book_title}'.",
    "Please renew '{book_title}' for me.",
]

FINE_INQUIRY_TEMPLATES = [
    "Do I have any outstanding fines?",
    "What fines are on my account?",
    "Can you check if I owe any fines?",
    "Show me my fines please.",
]

FINE_PAYMENT_TEMPLATES = [
    "I'd like to pay my fines.",
    "Can I pay off my outstanding fines?",
    "I want to settle my account balance.",
]

PATRON_SUMMARY_TEMPLATES = [
    "What's on my account right now?",
    "Can you show me my patron summary?",
    "What do I currently have checked out?",
    "Show me my account details.",
]

ILL_REQUEST_TEMPLATES = [
    "I need to request '{book_title}' from {partner_library}.",
    "Can you get '{book_title}' via inter-library loan from {partner_library}?",
    "I'd like to borrow '{book_title}' (ISBN: {isbn}) through ILL from {partner_library}.",
]

ILL_STATUS_TEMPLATES = [
    "What's the status of my inter-library loan requests?",
    "Can you check on my ILL requests?",
    "Do I have any pending inter-library loans?",
]

_TEMPLATES: dict[InteractionType, list[str]] = {
    InteractionType.CATALOG_SEARCH: CATALOG_SEARCH_TEMPLATES,
    InteractionType.BOOK_DETAIL: BOOK_DETAIL_TEMPLATES,
    InteractionType.AVAILABILITY_CHECK: AVAILABILITY_TEMPLATES,
    InteractionType.CHECKOUT: CHECKOUT_TEMPLATES,
    InteractionType.HOLD: HOLD_TEMPLATES,
    InteractionType.RETURN: RETURN_TEMPLATES,
    InteractionType.RENEWAL: RENEWAL_TEMPLATES,
    InteractionType.FINE_INQUIRY: FINE_INQUIRY_TEMPLATES,
    InteractionType.FINE_PAYMENT: FINE_PAYMENT_TEMPLATES,
    InteractionType.PATRON_SUMMARY: PATRON_SUMMARY_TEMPLATES,
    InteractionType.ILL_REQUEST: ILL_REQUEST_TEMPLATES,
    InteractionType.ILL_STATUS: ILL_STATUS_TEMPLATES,
}

# Edge case templates
_EDGE_CASE_TEMPLATES: dict[str, tuple[InteractionType, list[str]]] = {
    "blocked_patron_checkout": (
        InteractionType.CHECKOUT,
        [
            "I'd like to check out '{book_title}'. I know I might have some fines...",
            "Can I borrow '{book_title}'? I think my account might have an issue.",
        ],
    ),
    "at_limit_checkout": (
        InteractionType.CHECKOUT,
        [
            "I'd like to check out '{book_title}'. I already have quite a few books out.",
            "One more checkout please — '{book_title}'.",
        ],
    ),
    "duplicate_hold": (
        InteractionType.HOLD,
        [
            "Can you place another hold on '{book_title}' for me? I'm not sure if my first one went through.",
            "Put a hold on '{book_title}' again please.",
        ],
    ),
    "overdue_fine_inquiry": (
        InteractionType.FINE_INQUIRY,
        [
            "I think I have some overdue fines. Can you tell me how much I owe?",
            "My books are overdue — what do I owe?",
        ],
    ),
}

# Stateful sequence definitions: (type1, type2, ...) chains
_SEQUENCE_CHAINS: list[list[InteractionType]] = [
    [InteractionType.CATALOG_SEARCH, InteractionType.CHECKOUT],
    [InteractionType.BOOK_DETAIL, InteractionType.CHECKOUT],
    [InteractionType.CATALOG_SEARCH, InteractionType.HOLD],
    [InteractionType.CATALOG_SEARCH, InteractionType.CHECKOUT, InteractionType.RETURN],
    [InteractionType.PATRON_SUMMARY, InteractionType.FINE_PAYMENT],
]

# Types per domain
_DOMAIN_TYPES: dict[str, list[InteractionType]] = {
    "catalog": [
        InteractionType.CATALOG_SEARCH,
        InteractionType.BOOK_DETAIL,
        InteractionType.AVAILABILITY_CHECK,
    ],
    "circulation": [
        InteractionType.CHECKOUT,
        InteractionType.HOLD,
        InteractionType.RETURN,
        InteractionType.RENEWAL,
        InteractionType.FINE_INQUIRY,
        InteractionType.FINE_PAYMENT,
        InteractionType.PATRON_SUMMARY,
    ],
    "ill": [
        InteractionType.ILL_REQUEST,
        InteractionType.ILL_STATUS,
    ],
}


class PatronRequestGenerator:
    """Deterministic template-based generator for benchmark interactions."""

    def __init__(self, config: BenchmarkConfig) -> None:
        self._config = config
        self._rng = random_module.Random(config.random_seed)
        self._books = self._load_books()
        self._authors = self._load_authors()
        self._patrons = self._load_patrons()
        self._filtered_patrons = self._filter_patrons()
        self._counter = 0

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_books(self) -> list[dict[str, Any]]:
        if not _CATALOG_PATH.exists():
            return []
        data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        return data.get("books", [])

    def _load_authors(self) -> list[dict[str, Any]]:
        if not _CATALOG_PATH.exists():
            return []
        data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        authors_dict = data.get("authors", {})
        return [{"key": k, **v} for k, v in authors_dict.items()]

    def _load_patrons(self) -> list[dict[str, Any]]:
        if not _PATRONS_PATH.exists():
            return []
        return json.loads(_PATRONS_PATH.read_text(encoding="utf-8"))

    def _filter_patrons(self) -> list[dict[str, Any]]:
        pool_ids = set(self._config.patron_pool)
        cat_filter = (
            set(self._config.patron_category_filter)
            if self._config.patron_category_filter
            else None
        )
        result = [p for p in self._patrons if p["id"] in pool_ids]
        if cat_filter:
            result = [p for p in result if p.get("category", "") in cat_filter]
        return result or self._patrons[:1]  # fallback to first patron

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(self) -> list[BenchmarkInteraction]:
        """Generate all interactions according to config."""
        target = self._config.interaction_count
        interactions: list[BenchmarkInteraction] = []

        # Determine how many should be sequences vs standalone
        sequence_budget = 0
        if self._config.stateful_sequences and target >= 4:
            sequence_budget = max(1, int(target * 0.3))

        # Determine edge case budget (~10%)
        edge_budget = max(0, int(target * 0.1))

        standalone_budget = target - sequence_budget - edge_budget

        # Generate stateful sequences
        seq_generated = 0
        while seq_generated < sequence_budget:
            chain = self._rng.choice(_SEQUENCE_CHAINS)
            seq = self._generate_sequence(chain)
            if seq_generated + len(seq) > sequence_budget + 2:
                # Avoid overshooting too much
                break
            interactions.extend(seq)
            seq_generated += len(seq)

        # Generate edge cases
        edge_types = list(_EDGE_CASE_TEMPLATES.keys())
        for _ in range(edge_budget):
            edge_type = self._rng.choice(edge_types)
            interactions.append(self._generate_edge_case(edge_type))

        # Generate standalone interactions
        for _ in range(standalone_budget):
            itype = self._pick_interaction_type()
            interactions.append(self._generate_standalone(itype))

        # Shuffle to interleave sequences, edge cases, and standalone
        self._rng.shuffle(interactions)

        # Trim to exact target
        return interactions[:target]

    def _pick_interaction_type(self) -> InteractionType:
        """Pick an interaction type based on domain and complexity weights."""
        dw = self._config.domain_weights
        domain_weights = [
            ("catalog", dw.catalog),
            ("circulation", dw.circulation),
            ("ill", dw.ill),
        ]
        domain = self._weighted_choice(domain_weights)

        candidates = _DOMAIN_TYPES.get(domain, [])
        if not candidates:
            candidates = list(InteractionType)

        # Filter by complexity distribution
        cd = self._config.complexity_distribution
        complexity_weights = [
            ("simple", cd.simple),
            ("medium", cd.medium),
            ("complex", cd.complex),
        ]
        target_complexity = self._weighted_choice(complexity_weights)

        matching = [
            t for t in candidates
            if INTERACTION_COMPLEXITY.get(t) == target_complexity
        ]
        if not matching:
            matching = candidates

        return self._rng.choice(matching)

    def _weighted_choice(self, items: list[tuple[str, float]]) -> str:
        """Weighted random selection from (label, weight) pairs."""
        labels = [item[0] for item in items]
        weights = [max(item[1], 0.0) for item in items]
        total = sum(weights)
        if total <= 0:
            return self._rng.choice(labels)
        return self._rng.choices(labels, weights=weights, k=1)[0]

    def _generate_standalone(
        self, itype: InteractionType
    ) -> BenchmarkInteraction:
        """Generate a single standalone interaction."""
        patron = self._rng.choice(self._filtered_patrons)
        book = self._rng.choice(self._books) if self._books else None
        return self._build_interaction(itype, patron, book)

    def _generate_sequence(
        self, chain: list[InteractionType]
    ) -> list[BenchmarkInteraction]:
        """Generate a stateful multi-step sequence."""
        patron = self._rng.choice(self._filtered_patrons)
        book = self._rng.choice(self._books) if self._books else None
        seq_id = f"seq-{self._counter:04d}"
        self._counter += 1

        interactions = []
        for order, itype in enumerate(chain):
            ix = self._build_interaction(
                itype, patron, book, sequence_id=seq_id, sequence_order=order
            )
            interactions.append(ix)
        return interactions

    def _generate_edge_case(self, edge_type: str) -> BenchmarkInteraction:
        """Generate an edge case interaction."""
        itype, templates = _EDGE_CASE_TEMPLATES[edge_type]
        patron = self._rng.choice(self._filtered_patrons)
        book = self._rng.choice(self._books) if self._books else None

        template = self._rng.choice(templates)
        message = self._fill_template(template, book, patron)

        self._counter += 1
        return BenchmarkInteraction(
            interaction_id=f"bm-{self._counter:04d}",
            patron_id=patron["id"],
            patron_name=patron.get("name", ""),
            patron_category=patron.get("category", "adult"),
            message=message,
            interaction_type=itype,
            expected_domain=INTERACTION_DOMAIN[itype],
            expected_tool_hints=TOOL_HINTS.get(itype, []),
            complexity_tier=INTERACTION_COMPLEXITY[itype],
            is_edge_case=True,
            edge_case_type=edge_type,
        )

    def _build_interaction(
        self,
        itype: InteractionType,
        patron: dict[str, Any],
        book: dict[str, Any] | None,
        sequence_id: str | None = None,
        sequence_order: int = 0,
    ) -> BenchmarkInteraction:
        """Build a BenchmarkInteraction from type, patron, and book."""
        templates = _TEMPLATES.get(itype, ["Hello."])
        template = self._rng.choice(templates)
        message = self._fill_template(template, book, patron)

        self._counter += 1
        return BenchmarkInteraction(
            interaction_id=f"bm-{self._counter:04d}",
            sequence_id=sequence_id,
            sequence_order=sequence_order,
            patron_id=patron["id"],
            patron_name=patron.get("name", ""),
            patron_category=patron.get("category", "adult"),
            message=message,
            interaction_type=itype,
            expected_domain=INTERACTION_DOMAIN[itype],
            expected_tool_hints=TOOL_HINTS.get(itype, []),
            complexity_tier=INTERACTION_COMPLEXITY[itype],
        )

    def _fill_template(
        self,
        template: str,
        book: dict[str, Any] | None,
        patron: dict[str, Any],
    ) -> str:
        """Fill a message template with book/patron/partner data."""
        book = book or {}
        partner = self._rng.choice(PARTNER_LIBRARIES)
        genres = book.get("genres", ["literature"])

        return template.format(
            book_title=book.get("title", "a book"),
            author=book.get("author", "an author"),
            isbn=book.get("isbn", "978-0-HANNO-0000"),
            genre=self._rng.choice(genres) if genres else "literature",
            stratum=book.get("stratum", 1),
            patron_name=patron.get("name", "Patron"),
            partner_library=partner[1],
        )
