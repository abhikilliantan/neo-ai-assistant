"""Declarative base for all ORM models (SQLAlchemy 2.x style)."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Root declarative base. Models inherit from this."""
