"""Shared error response schema."""

from typing import Any

from pydantic import BaseModel


class ErrorBody(BaseModel):
    error: str
    message: str
    details: Any | None = None
