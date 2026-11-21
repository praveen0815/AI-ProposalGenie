"""Structured audit events. Messages name the action, not secrets or document text."""

import logging

logger = logging.getLogger("app.audit")


def audit(action: str, *, actor_id: object = None, company_id: object = None, resource_id: object = None) -> None:
    logger.info(
        "audit action=%s actor=%s company=%s resource=%s",
        action,
        actor_id or "-",
        company_id or "-",
        resource_id or "-",
    )
