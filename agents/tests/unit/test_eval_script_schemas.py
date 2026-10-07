"""Unit tests for eval script Pydantic schemas."""

import json

import pytest
from pydantic import ValidationError

from shared.eval.eval_script_schemas import (
    EvalScript,
    EvalScriptCatalog,
    EvalStep,
    StepAssertion,
)


class TestStepAssertion:
    """Validate StepAssertion model."""

    def test_valid_assertion(self):
        a = StepAssertion(
            service="catalog",
            endpoint="/books/book-001",
            field_path="title",
            expected_value="Tusk and Bone",
        )
        assert a.service == "catalog"
        assert a.endpoint == "/books/book-001"

    def test_invalid_service_rejected(self):
        with pytest.raises(ValidationError):
            StepAssertion(
                service="invalid_service",
                endpoint="/foo",
                field_path="bar",
                expected_value="baz",
            )

    def test_expected_value_accepts_any_type(self):
        a = StepAssertion(
            service="circulation",
            endpoint="/patrons/patron-001",
            field_path="status",
            expected_value=True,
        )
        assert a.expected_value is True

        b = StepAssertion(
            service="ill",
            endpoint="/requests",
            field_path="count",
            expected_value=42,
        )
        assert b.expected_value == 42


class TestEvalStep:
    """Validate EvalStep model."""

    def test_minimal_step(self):
        step = EvalStep(
            step_id="step_1",
            order=1,
            patron_message="Hello",
        )
        assert step.step_id == "step_1"
        assert step.expected_tool_calls == []
        assert step.response_must_contain == []
        assert step.response_must_not_contain == []
        assert step.state_assertions == []
        assert step.timeout_seconds == 30

    def test_full_step(self):
        step = EvalStep(
            step_id="step_1",
            order=1,
            patron_message="Search for elephant books",
            expected_tool_calls=["search_books"],
            response_must_contain=["elephant"],
            response_must_not_contain=["error"],
            state_assertions=[
                StepAssertion(
                    service="catalog",
                    endpoint="/books/book-001",
                    field_path="title",
                    expected_value="Tusk and Bone",
                ),
            ],
            timeout_seconds=60,
        )
        assert len(step.expected_tool_calls) == 1
        assert len(step.state_assertions) == 1
        assert step.timeout_seconds == 60

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            EvalStep(order=1, patron_message="Hello")  # missing step_id


class TestEvalScript:
    """Validate EvalScript model."""

    def test_minimal_script(self):
        script = EvalScript(
            scenario_id="s1",
            patron_id="patron-001",
        )
        assert script.scenario_id == "s1"
        assert script.patron_name == ""
        assert script.patron_role == "patron"
        assert script.skip_live_eval is False
        assert script.steps == []

    def test_skip_live_eval(self):
        script = EvalScript(
            scenario_id="s1",
            patron_id="patron-001",
            skip_live_eval=True,
            skip_reason="Requires chaos injection",
        )
        assert script.skip_live_eval is True
        assert script.skip_reason == "Requires chaos injection"

    def test_invalid_patron_role(self):
        with pytest.raises(ValidationError):
            EvalScript(
                scenario_id="s1",
                patron_id="patron-001",
                patron_role="admin",  # not in Literal["patron", "staff"]
            )


class TestEvalScriptCatalog:
    """Validate EvalScriptCatalog model and JSON round-trip."""

    def test_empty_catalog(self):
        catalog = EvalScriptCatalog()
        assert catalog.schema_version == "1.0"
        assert catalog.scripts == {}

    def test_catalog_with_scripts(self):
        catalog = EvalScriptCatalog(
            schema_version="1.0",
            scripts={
                "s1": EvalScript(
                    scenario_id="s1",
                    patron_id="patron-001",
                    steps=[
                        EvalStep(step_id="step_1", order=1, patron_message="Hello"),
                    ],
                ),
            },
        )
        assert "s1" in catalog.scripts
        assert len(catalog.scripts["s1"].steps) == 1

    def test_json_round_trip(self):
        catalog = EvalScriptCatalog(
            scripts={
                "s1": EvalScript(
                    scenario_id="s1",
                    patron_id="patron-001",
                    patron_name="Test User",
                    steps=[
                        EvalStep(
                            step_id="step_1",
                            order=1,
                            patron_message="Search for books",
                            expected_tool_calls=["search_books"],
                        ),
                    ],
                ),
            },
        )
        json_str = catalog.model_dump_json()
        loaded = EvalScriptCatalog.model_validate_json(json_str)
        assert loaded.scripts["s1"].patron_id == "patron-001"
        assert loaded.scripts["s1"].steps[0].expected_tool_calls == ["search_books"]

    def test_loads_from_file(self):
        """Validate that the actual eval scripts JSON parses successfully."""
        import pathlib

        scripts_path = (
            pathlib.Path(__file__).resolve().parents[3]
            / "tests"
            / "scenarios"
            / "scenario_eval_scripts.json"
        )
        if scripts_path.exists():
            catalog = EvalScriptCatalog.model_validate_json(
                scripts_path.read_text(encoding="utf-8")
            )
            assert len(catalog.scripts) > 0
            for sid, script in catalog.scripts.items():
                assert script.scenario_id == sid
