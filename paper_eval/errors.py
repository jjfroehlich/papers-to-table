class EvaluationError(Exception):
    """Base evaluator error."""


class ContractError(EvaluationError):
    """Raised when the published artifact contract is missing or inconsistent."""


class CliUsageError(EvaluationError):
    """Raised for invalid CLI input combinations."""
