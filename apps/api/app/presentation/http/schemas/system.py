"""Pydantic v2 schemas for /health and /ready."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str


class DependencyStatus(BaseModel):
    name: str
    ok: bool


class ReadinessResponse(BaseModel):
    status: str
    dependencies: list[DependencyStatus]
