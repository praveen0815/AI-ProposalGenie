"""Allowed proposal status changes."""

from app.models.enums import ApprovalAction, MembershipRole, ProposalStatus

_SOURCES: dict[ApprovalAction, set[ProposalStatus]] = {
    ApprovalAction.SUBMIT: {ProposalStatus.DRAFT, ProposalStatus.REJECTED},
    ApprovalAction.APPROVE: {ProposalStatus.REVIEW},
    ApprovalAction.REQUEST_CHANGES: {ProposalStatus.REVIEW},
    ApprovalAction.REJECT: {ProposalStatus.REVIEW},
    ApprovalAction.SEND: {ProposalStatus.APPROVED},
    ApprovalAction.ARCHIVE: {
        ProposalStatus.DRAFT,
        ProposalStatus.REVIEW,
        ProposalStatus.APPROVED,
        ProposalStatus.SENT,
        ProposalStatus.REJECTED,
    },
}

_TARGETS: dict[ApprovalAction, ProposalStatus] = {
    ApprovalAction.SUBMIT: ProposalStatus.REVIEW,
    ApprovalAction.APPROVE: ProposalStatus.APPROVED,
    ApprovalAction.REQUEST_CHANGES: ProposalStatus.DRAFT,
    ApprovalAction.REJECT: ProposalStatus.REJECTED,
    ApprovalAction.SEND: ProposalStatus.SENT,
    ApprovalAction.ARCHIVE: ProposalStatus.ARCHIVED,
}

_ADMIN_ACTIONS = {
    ApprovalAction.APPROVE,
    ApprovalAction.REQUEST_CHANGES,
    ApprovalAction.REJECT,
    ApprovalAction.SEND,
    ApprovalAction.ARCHIVE,
}

_COMMENT_REQUIRED = {ApprovalAction.REQUEST_CHANGES, ApprovalAction.REJECT}


class TransitionError(Exception):
    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.status_code = status_code


def transition(
    current: ProposalStatus,
    action: ApprovalAction,
    role: MembershipRole,
    comment: str | None,
) -> ProposalStatus:
    if current == ProposalStatus.GENERATING:
        raise TransitionError("Wait until generation finishes before changing the status")
    if current not in _SOURCES[action]:
        raise TransitionError(f"A proposal in {current.value} cannot use {action.value.lower().replace('_', ' ')}")
    if action in _ADMIN_ACTIONS and role not in {MembershipRole.OWNER, MembershipRole.ADMIN}:
        raise TransitionError("You do not have permission to perform this action", 403)
    if action in _COMMENT_REQUIRED and not (comment or "").strip():
        raise TransitionError("Add a comment explaining this decision", 422)
    return _TARGETS[action]


def action_for_target(current: ProposalStatus, target: ProposalStatus) -> ApprovalAction | None:
    for action, destination in _TARGETS.items():
        if destination == target and current in _SOURCES[action]:
            return action
    return None
