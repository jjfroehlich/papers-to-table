"""Tests for run lifecycle state transitions."""
from __future__ import annotations

import pytest

from backend.app.lifecycle import (
    VALID_TRANSITIONS,
    LifecycleError,
    apply_transition,
    validate_transition,
)
from backend.app.schemas import RunStatus


def make_run_data(status: RunStatus, **kwargs) -> dict:
    return {
        "status": status.value,
        "started_at": None,
        "completed_at": None,
        **kwargs,
    }


class TestValidTransitions:
    def test_created_to_validating(self):
        validate_transition(RunStatus.created, RunStatus.validating)

    def test_created_to_failed(self):
        validate_transition(RunStatus.created, RunStatus.failed)

    def test_validating_to_running(self):
        validate_transition(RunStatus.validating, RunStatus.running)

    def test_validating_to_failed(self):
        validate_transition(RunStatus.validating, RunStatus.failed)

    def test_running_to_completed(self):
        validate_transition(RunStatus.running, RunStatus.completed)

    def test_running_to_completed_with_warnings(self):
        validate_transition(RunStatus.running, RunStatus.completed_with_warnings)

    def test_running_to_failed(self):
        validate_transition(RunStatus.running, RunStatus.failed)

    def test_running_to_interrupted(self):
        validate_transition(RunStatus.running, RunStatus.interrupted)


class TestInvalidTransitions:
    def test_created_to_running(self):
        with pytest.raises(LifecycleError):
            validate_transition(RunStatus.created, RunStatus.running)

    def test_created_to_completed(self):
        with pytest.raises(LifecycleError):
            validate_transition(RunStatus.created, RunStatus.completed)

    def test_validating_to_completed(self):
        with pytest.raises(LifecycleError):
            validate_transition(RunStatus.validating, RunStatus.completed)

    def test_completed_to_anything(self):
        for target in RunStatus:
            with pytest.raises(LifecycleError):
                validate_transition(RunStatus.completed, target)

    def test_failed_to_anything(self):
        for target in RunStatus:
            with pytest.raises(LifecycleError):
                validate_transition(RunStatus.failed, target)

    def test_interrupted_to_anything(self):
        for target in RunStatus:
            with pytest.raises(LifecycleError):
                validate_transition(RunStatus.interrupted, target)

    def test_completed_with_warnings_terminal(self):
        for target in RunStatus:
            with pytest.raises(LifecycleError):
                validate_transition(RunStatus.completed_with_warnings, target)


class TestApplyTransition:
    def test_sets_status(self):
        data = make_run_data(RunStatus.created)
        updated = apply_transition(data, RunStatus.validating)
        assert updated["status"] == RunStatus.validating.value

    def test_sets_started_at_on_validating(self):
        data = make_run_data(RunStatus.created)
        updated = apply_transition(data, RunStatus.validating)
        assert updated["started_at"] is not None

    def test_does_not_overwrite_started_at(self):
        data = make_run_data(RunStatus.validating, started_at="2024-01-01T00:00:00+00:00")
        updated = apply_transition(data, RunStatus.running)
        assert updated["started_at"] == "2024-01-01T00:00:00+00:00"

    def test_sets_completed_at_on_terminal(self):
        for terminal in [RunStatus.completed, RunStatus.completed_with_warnings,
                         RunStatus.failed, RunStatus.interrupted]:
            data = make_run_data(RunStatus.running, started_at="2024-01-01T00:00:00+00:00")
            updated = apply_transition(data, terminal)
            assert updated["completed_at"] is not None

    def test_does_not_mutate_original(self):
        data = make_run_data(RunStatus.created)
        original_status = data["status"]
        apply_transition(data, RunStatus.validating)
        assert data["status"] == original_status

    def test_passes_kwargs(self):
        data = make_run_data(RunStatus.running, started_at="2024-01-01T00:00:00+00:00")
        updated = apply_transition(data, RunStatus.failed, error_message="Something went wrong")
        assert updated["error_message"] == "Something went wrong"

    def test_invalid_transition_raises(self):
        data = make_run_data(RunStatus.completed)
        with pytest.raises(LifecycleError):
            apply_transition(data, RunStatus.running)
