from __future__ import annotations

from datetime import datetime, timezone

from .schemas import RunStatus

VALID_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.created: {RunStatus.validating, RunStatus.failed},
    RunStatus.validating: {RunStatus.running, RunStatus.failed},
    RunStatus.running: {
        RunStatus.completed,
        RunStatus.completed_with_warnings,
        RunStatus.failed,
        RunStatus.interrupted,
    },
    RunStatus.completed: set(),
    RunStatus.completed_with_warnings: set(),
    RunStatus.failed: set(),
    RunStatus.interrupted: set(),
}


class LifecycleError(Exception):
    pass


def validate_transition(current: RunStatus, next_status: RunStatus) -> None:
    allowed = VALID_TRANSITIONS.get(current, set())
    if next_status not in allowed:
        raise LifecycleError(
            f"Invalid state transition: {current.value} -> {next_status.value}"
        )


def apply_transition(run_data: dict, next_status: RunStatus, **kwargs) -> dict:
    """Apply a state transition to run data dict, return updated dict."""
    current = RunStatus(run_data["status"])
    validate_transition(current, next_status)
    run_data = dict(run_data)
    run_data["status"] = next_status.value
    now = datetime.now(timezone.utc).isoformat()
    if next_status == RunStatus.validating and not run_data.get("started_at"):
        run_data["started_at"] = now
    if next_status in (
        RunStatus.completed,
        RunStatus.completed_with_warnings,
        RunStatus.failed,
        RunStatus.interrupted,
    ):
        run_data["completed_at"] = now
    for k, v in kwargs.items():
        run_data[k] = v
    return run_data
