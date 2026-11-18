"""Errors raised by a workflow node. Messages are safe to show to a user."""


class AgentWorkflowError(Exception):
    status_code = 503

    def __init__(self, message: str, node: str) -> None:
        super().__init__(message)
        self.node = node


class AgentOutputError(AgentWorkflowError):
    """The model response did not match the agent's schema."""

    status_code = 502
