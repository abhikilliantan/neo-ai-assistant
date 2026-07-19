"""create neo_app role and grants

Revision ID: f9c8a2b1d3e4
Revises: d68d0f6a4fa8
Create Date: 2026-07-19 07:00:00.000000

Provisions a NON-superuser, NON-BYPASSRLS runtime role (`neo_app`) so that
RLS policies (with FORCE) actually apply at request time. `neo` (owner) is
kept for migrations and the tiny privileged system boundary.

Password: dev default is `neo_app`. Prod pre-provisions the role with a
secret via IaC; the `DO $$ IF NOT EXISTS` guard turns this migration into
a no-op there. GRANTs remain idempotent.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f9c8a2b1d3e4"
down_revision: str | None = "d68d0f6a4fa8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'neo_app') THEN
            CREATE ROLE neo_app LOGIN PASSWORD 'neo_app' NOSUPERUSER NOBYPASSRLS;
          END IF;
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO neo_app;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO neo_app;")
    # Cover future tables created by `neo` (the migration owner).
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE neo IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO neo_app;"
    )


def downgrade() -> None:
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE neo IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM neo_app;"
    )
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM neo_app;")
    op.execute("REVOKE ALL ON SCHEMA public FROM neo_app;")
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'neo_app') THEN
            DROP ROLE neo_app;
          END IF;
        END
        $$;
        """
    )
