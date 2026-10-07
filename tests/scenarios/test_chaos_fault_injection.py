"""Unit tests for the ChaosController and FaultProfile schema."""

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable.
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from chaos_profiles import (
    BUILTIN_PROFILES,
    FaultEvent,
    FaultProfile,
    FaultType,
    load_profile,
)
from chaos_controller import ChaosController


class TestChaosControllerDeterminism:
    """Verify deterministic replay and call-index scheduling."""

    def test_deterministic_replay(self):
        """Same seed + profile produces identical fault sequence across 2 runs."""
        profile = load_profile("registry_intermittent", seed=42)

        faults_run1 = []
        ctrl1 = ChaosController(profile)
        for _ in range(4):
            event = ctrl1.intercept("registry", "/a2a/message/send")
            faults_run1.append(event)

        faults_run2 = []
        ctrl2 = ChaosController(profile)
        for _ in range(4):
            event = ctrl2.intercept("registry", "/a2a/message/send")
            faults_run2.append(event)

        # Both runs should produce identical event sequences.
        assert len(faults_run1) == len(faults_run2)
        for a, b in zip(faults_run1, faults_run2):
            if a is None:
                assert b is None
            else:
                assert b is not None
                assert a.call_index == b.call_index
                assert a.fault_type == b.fault_type

    def test_respects_call_index(self):
        """Fault triggers only at the specified call_index."""
        profile = load_profile("a2a_timeout_on_send", seed=42)
        ctrl = ChaosController(profile)

        # call_index 0 should fire
        event0 = ctrl.intercept("registry", "/a2a/message/send")
        assert event0 is not None
        assert event0.fault_type == FaultType.TIMEOUT

        # call_index 1 should NOT fire (no fault scheduled)
        event1 = ctrl.intercept("registry", "/a2a/message/send")
        assert event1 is None


class TestFaultTypeExceptions:
    """Each FaultType maps to the correct exception."""

    @pytest.mark.parametrize(
        "fault_type,expected_exc",
        [
            (FaultType.TIMEOUT, TimeoutError),
            (FaultType.HTTP_500, Exception),  # ServiceCallError
            (FaultType.INTERMITTENT_OUTAGE, Exception),  # ServiceUnavailableError
            (FaultType.CONNECTION_REFUSED, ConnectionError),
            (FaultType.MALFORMED_JSON, ValueError),
        ],
    )
    def test_fault_types_raise_correct_exceptions(self, fault_type, expected_exc):
        event = FaultEvent(
            call_index=0,
            fault_type=fault_type,
            target_service="test",
            target_endpoint="/test",
        )
        profile = FaultProfile(
            profile_id="test",
            seed=1,
            description="test",
            fault_events=[event],
        )
        ctrl = ChaosController(profile)
        with pytest.raises(expected_exc):
            ctrl.apply_fault(event)


class TestControllerState:
    """Test reset, summary, and budget tracking."""

    def test_reset_clears_state(self):
        """Reset returns controller to initial state."""
        profile = load_profile("a2a_timeout_on_send")
        ctrl = ChaosController(profile)

        # Fire a fault and record a retry.
        ctrl.intercept("registry", "/a2a/message/send")
        ctrl.record_retry()
        assert ctrl.retry_count == 1
        assert len(ctrl.fault_log) == 0  # fault_log only populated by apply_fault

        ctrl.reset()

        assert ctrl.retry_count == 0
        assert len(ctrl.fault_log) == 0
        # After reset, call_index 0 should fire again.
        event = ctrl.intercept("registry", "/a2a/message/send")
        assert event is not None

    def test_summary_contains_required_fields(self):
        """Summary dict matches chaos-report schema requirements."""
        profile = load_profile("a2a_timeout_on_send")
        ctrl = ChaosController(profile)
        summary = ctrl.summary()

        required_keys = {
            "profile_id",
            "seed",
            "total_faults_injected",
            "total_retries",
            "retry_budget",
            "budget_respected",
            "expected_degradation_mode",
            "fault_log",
        }
        assert required_keys <= set(summary.keys())

    def test_retry_budget_tracked(self):
        """Budget violations are detected."""
        profile = FaultProfile(
            profile_id="tight_budget",
            seed=1,
            description="test",
            max_retry_budget=2,
        )
        ctrl = ChaosController(profile)

        ctrl.record_retry()
        ctrl.record_retry()
        assert ctrl.retry_budget_check() is True

        ctrl.record_retry()
        assert ctrl.retry_budget_check() is False


class TestProfileSerialization:
    """Verify lossless JSON serialization round-trip."""

    def test_profile_serialization_roundtrip(self):
        profile = load_profile("registry_intermittent")
        json_str = profile.to_json()
        restored = FaultProfile.from_json(json_str)

        assert restored.profile_id == profile.profile_id
        assert restored.seed == profile.seed
        assert len(restored.fault_events) == len(profile.fault_events)
        for orig, rest in zip(profile.fault_events, restored.fault_events):
            assert orig.call_index == rest.call_index
            assert orig.fault_type == rest.fault_type
            assert orig.target_service == rest.target_service


class TestBuiltinProfiles:
    """Verify all built-in profiles are loadable."""

    def test_builtin_profiles_exist(self):
        expected = {
            "a2a_timeout_on_send",
            "catalog_500_on_search",
            "registry_intermittent",
            "malformed_a2a_response",
        }
        assert expected == set(BUILTIN_PROFILES.keys())

        for profile_id in expected:
            profile = load_profile(profile_id)
            assert profile.profile_id == profile_id
            assert len(profile.fault_events) > 0


class TestChaosFixtureIntegration:
    """Verify fixture behavior without @chaos_profile marker."""

    def test_no_chaos_marker_means_no_faults(self, chaos_controller):
        """Without @pytest.mark.chaos_profile, controller should be None."""
        assert chaos_controller is None
