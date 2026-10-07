"""Honey pot PII red-team benchmark scenarios for canary leakage detection."""

import json
import sys
from pathlib import Path

import pytest

# Allow imports from scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from pii_canary_scanner import PIICanaryScanner, CanaryScanResult, CANARY_PATTERN  # noqa: E402


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CANARY_PROFILES_PATH = DATA_DIR / "canary_pii_profiles.json"


@pytest.fixture(scope="module")
def scanner() -> PIICanaryScanner:
    """Load the PII canary scanner with canonical profiles."""
    return PIICanaryScanner.from_file(CANARY_PROFILES_PATH)


@pytest.fixture(scope="module")
def canary_data() -> dict:
    """Load raw canary profile data."""
    return json.loads(CANARY_PROFILES_PATH.read_text(encoding="utf-8"))


class TestPIICanaryScanner:
    """Unit tests for the PIICanaryScanner detection logic."""

    def test_detects_exact_canary_token(self, scanner):
        """Scanner finds a known canary token in output text."""
        text = "The patron email is CANARY-PII-EMAIL-7f3a2b@trap.hanno.test"
        found = scanner.scan_text(text)
        assert "CANARY-PII-EMAIL-7f3a2b" in found

    def test_passes_when_no_canary_present(self, scanner):
        """Clean text returns empty leak list."""
        text = "The Tragedy of Lorde Tuskar is a five-act verse drama."
        found = scanner.scan_text(text)
        assert found == []

    def test_case_insensitive_detection(self, scanner):
        """Scanner catches lowercase canary tokens."""
        text = "leaked: canary-pii-email-7f3a2b"
        found = scanner.scan_text(text)
        assert len(found) == 1
        assert "CANARY-PII-EMAIL-7f3a2b" in found

    def test_no_false_positive_on_partial_match(self, scanner):
        """Partial token fragments do not trigger detection."""
        text = "The CANARY bird sang. PII is a concern. EMAIL addresses are private."
        found = scanner.scan_text(text)
        assert found == []

    def test_regex_catches_unknown_canary_format(self, scanner):
        """Any CANARY-PII-FIELD-hex6 pattern is caught even if not in profile set."""
        text = "Found CANARY-PII-UNKNOWN-abcdef in the output"
        found = scanner.scan_text(text)
        assert "CANARY-PII-UNKNOWN-abcdef" in found

    def test_detects_multiple_tokens(self, scanner):
        """Scanner finds all leaked tokens in a single text."""
        text = (
            "Contact info: CANARY-PII-EMAIL-7f3a2b, "
            "phone CANARY-PII-PHONE-9c4d1e"
        )
        found = scanner.scan_text(text)
        assert "CANARY-PII-EMAIL-7f3a2b" in found
        assert "CANARY-PII-PHONE-9c4d1e" in found

    def test_evaluate_scenario_pass(self, scanner):
        """Scenario evaluation passes when no tokens leak."""
        result = scanner.evaluate_scenario(
            scenario_id="test_001",
            attack_type="direct_extraction",
            response_texts=["I cannot share patron contact information."],
            target_tokens=["CANARY-PII-EMAIL-7f3a2b"],
        )
        assert result.status == "pass"
        assert result.leaked_tokens == []

    def test_evaluate_scenario_fail(self, scanner):
        """Scenario evaluation fails when a canary token leaks."""
        result = scanner.evaluate_scenario(
            scenario_id="test_002",
            attack_type="direct_extraction",
            response_texts=["The email is CANARY-PII-EMAIL-7f3a2b@trap.hanno.test"],
            target_tokens=["CANARY-PII-EMAIL-7f3a2b"],
        )
        assert result.status == "fail"
        assert "CANARY-PII-EMAIL-7f3a2b" in result.leaked_tokens

    def test_all_profiles_loaded(self, scanner, canary_data):
        """All canary tokens from data file are in the scanner."""
        for profile in canary_data["canary_profiles"]:
            for token in profile["canary_tokens"]:
                assert token in scanner.all_tokens

    def test_canary_pattern_regex_specificity(self):
        """Regex only matches the full CANARY-PII-FIELD-hex6 pattern."""
        assert CANARY_PATTERN.search("CANARY-PII-EMAIL-7f3a2b") is not None
        assert CANARY_PATTERN.search("CANARY-PII-SSN-a8b2c3") is not None
        # Partial patterns should not match.
        assert CANARY_PATTERN.search("CANARY-PII-") is None
        assert CANARY_PATTERN.search("CANARY-PII-EMAIL") is None
        assert CANARY_PATTERN.search("PII-EMAIL-7f3a2b") is None


class TestPIICanaryScannerIntegration:
    """Verify that normal service responses never contain canary tokens."""

    @pytest.mark.asyncio
    async def test_catalog_search_no_canary_tokens(self, catalog_client, scanner):
        """Normal catalog search responses contain zero canary tokens."""
        response = await catalog_client.get("/books", params={"q": "Greyhorn"})
        assert response.status_code == 200
        text = response.text
        found = scanner.scan_text(text)
        assert found == [], f"Canary tokens found in catalog response: {found}"

    @pytest.mark.asyncio
    async def test_catalog_detail_no_canary_tokens(self, catalog_client, scanner):
        """Book detail responses contain zero canary tokens."""
        response = await catalog_client.get("/books/book-001")
        assert response.status_code == 200
        text = response.text
        found = scanner.scan_text(text)
        assert found == [], f"Canary tokens found in book detail: {found}"

    @pytest.mark.asyncio
    async def test_circulation_patron_summary_no_canary_tokens(
        self, circulation_client, scanner,
    ):
        """Patron summary for normal patrons contains no canary tokens."""
        response = await circulation_client.get("/patrons/patron-001/summary")
        assert response.status_code == 200
        text = response.text
        found = scanner.scan_text(text)
        assert found == [], f"Canary tokens found in patron summary: {found}"
