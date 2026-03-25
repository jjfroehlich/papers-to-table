from __future__ import annotations

from .schemas import OperatorRunStatus, RunStatus


ALLOWED_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.CREATED: {RunStatus.VALIDATING, RunStatus.FAILED, RunStatus.INTERRUPTED},
    RunStatus.VALIDATING: {RunStatus.RUNNING, RunStatus.FAILED, RunStatus.INTERRUPTED},
    RunStatus.RUNNING: {
        RunStatus.COMPLETED,
        RunStatus.COMPLETED_WITH_WARNINGS,
        RunStatus.FAILED,
        RunStatus.INTERRUPTED,
    },
    RunStatus.COMPLETED: set(),
    RunStatus.COMPLETED_WITH_WARNINGS: set(),
    RunStatus.FAILED: set(),
    RunStatus.INTERRUPTED: set(),
}


def can_transition(current: RunStatus, target: RunStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


def map_operator_status(status: RunStatus) -> OperatorRunStatus:
    if status == RunStatus.CREATED:
        return OperatorRunStatus.READY
    if status == RunStatus.VALIDATING:
        return OperatorRunStatus.VALIDATING
    if status == RunStatus.RUNNING:
        return OperatorRunStatus.RUNNING
    if status == RunStatus.COMPLETED:
        return OperatorRunStatus.COMPLETED
    if status == RunStatus.COMPLETED_WITH_WARNINGS:
        return OperatorRunStatus.COMPLETED_WITH_WARNINGS
    return OperatorRunStatus.FAILED
