from backend.app.lifecycle import can_transition, map_operator_status
from backend.app.schemas import OperatorRunStatus, RunStatus


def test_lifecycle_allows_core_transitions() -> None:
    assert can_transition(RunStatus.CREATED, RunStatus.VALIDATING)
    assert can_transition(RunStatus.VALIDATING, RunStatus.RUNNING)
    assert can_transition(RunStatus.RUNNING, RunStatus.COMPLETED)


def test_lifecycle_rejects_invalid_transition() -> None:
    assert not can_transition(RunStatus.CREATED, RunStatus.COMPLETED)


def test_operator_status_mapping() -> None:
    assert map_operator_status(RunStatus.CREATED) == OperatorRunStatus.READY
    assert map_operator_status(RunStatus.COMPLETED_WITH_WARNINGS) == OperatorRunStatus.COMPLETED_WITH_WARNINGS
    assert map_operator_status(RunStatus.FAILED) == OperatorRunStatus.FAILED
