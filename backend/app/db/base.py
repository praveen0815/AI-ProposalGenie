"""Declarative SQLAlchemy base shared by models and Alembic."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for future ORM models."""
