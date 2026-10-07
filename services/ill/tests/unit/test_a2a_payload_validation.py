"""Tests for A2A outbound payload validation."""

import pytest

from ill.a2a_client import (
    PROHIBITED_PAYLOAD_FIELDS,
    _validate_outbound_payload,
)


class TestA2APayloadValidation:
    """Verify outbound A2A payload validation rejects PII fields."""

    def test_rejects_email_in_payload(self):
        """Payload with 'email' field raises ValueError."""
        with pytest.raises(ValueError, match="email"):
            _validate_outbound_payload({"email": "test@example.com", "book_id": "b1"})

    def test_rejects_phone_in_payload(self):
        """Payload with 'phone' field raises ValueError."""
        with pytest.raises(ValueError, match="phone"):
            _validate_outbound_payload({"phone": "555-0101", "book_id": "b1"})

    def test_rejects_ssn_in_payload(self):
        """Payload with 'ssn' field raises ValueError."""
        with pytest.raises(ValueError, match="ssn"):
            _validate_outbound_payload({"ssn": "XXX-XX-1234"})

    def test_rejects_address_in_payload(self):
        """Payload with 'address' field raises ValueError."""
        with pytest.raises(ValueError, match="address"):
            _validate_outbound_payload({"address": "123 Main St"})

    def test_rejects_card_number_in_payload(self):
        """Payload with 'card_number' field raises ValueError."""
        with pytest.raises(ValueError, match="card_number"):
            _validate_outbound_payload({"card_number": "4111111111111111"})

    def test_rejects_patron_prefixed_fields(self):
        """Payload with patron_email, patron_phone etc. raises ValueError."""
        with pytest.raises(ValueError):
            _validate_outbound_payload({"patron_email": "test@example.com"})
        with pytest.raises(ValueError):
            _validate_outbound_payload({"patron_phone": "555-0101"})

    def test_allows_clean_payload(self):
        """Payload with only book metadata passes validation."""
        _validate_outbound_payload({
            "book_id": "book-001",
            "title": "The Tragedy of Lorde Tuskar",
            "author": "Maren Greyhorn",
            "isbn": "978-0-HANNO-0001",
            "patron_id": "patron-001",
            "patron_reference": "HAN-P-001",
        })

    def test_rejects_multiple_pii_fields(self):
        """All prohibited fields are caught and reported."""
        with pytest.raises(ValueError) as exc_info:
            _validate_outbound_payload({
                "email": "a@b.com",
                "phone": "555",
                "ssn": "123",
            })
        error_msg = str(exc_info.value)
        assert "email" in error_msg
        assert "phone" in error_msg
        assert "ssn" in error_msg

    def test_prohibited_fields_set_is_comprehensive(self):
        """The prohibited set covers all expected PII field names."""
        expected = {"email", "phone", "ssn", "address", "card_number",
                    "patron_email", "patron_phone", "patron_address", "patron_ssn"}
        assert expected.issubset(PROHIBITED_PAYLOAD_FIELDS)
