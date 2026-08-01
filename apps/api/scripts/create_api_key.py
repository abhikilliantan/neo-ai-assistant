"""Mint a service API key from the CLI (operator/seed path).

Creates a key for an existing organization DIRECTLY on the privileged `neo`
system session — the same posture as scripts/create_user.py: no HTTP surface, no
tokens, not subject to any request-time auth. Use it to get the FIRST key for
n8n before the management UI exists.

The plaintext secret is printed ONCE and never stored (only its hash + prefix
go to the DB). Reuses the SAME generation + repository code the HTTP route uses —
no new crypto.

Run inside the api container:
    make create-api-key ORG=acme NAME="n8n"                 # org by slug
    python -m scripts.create_api_key --org-slug acme --name n8n
    python -m scripts.create_api_key --org-id <uuid> --name n8n
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases import api_keys as api_keys_uc
from app.infrastructure.config import get_settings
from app.infrastructure.db.models import Organization
from app.infrastructure.db.repositories import ApiKeyRepository
from app.infrastructure.db.session import build_system_database


async def _resolve_org(
    session: AsyncSession, *, org_id: str | None, org_slug: str | None
) -> Organization | None:
    if org_id is not None:
        return await session.get(Organization, UUID(org_id))
    stmt = select(Organization).where(Organization.slug == org_slug)
    return (await session.execute(stmt)).scalar_one_or_none()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="create_api_key",
        description="Mint a service API key for an existing organization.",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--org-slug", help="organization slug (e.g. 'acme')")
    target.add_argument("--org-id", help="organization UUID")
    parser.add_argument("--name", required=True, help="human label for the key")
    parser.add_argument(
        "--scope",
        action="append",
        dest="scopes",
        default=None,
        help="scope to grant (repeatable); default: read",
    )
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    db = build_system_database(get_settings())
    try:
        async with db.sessionmaker() as session:
            org = await _resolve_org(session, org_id=args.org_id, org_slug=args.org_slug)
            if org is None:
                target = args.org_id or args.org_slug
                print(f"error: organization {target!r} not found", file=sys.stderr)
                return 1
            key, raw = await api_keys_uc.create_api_key(
                organization_id=org.id,
                name=args.name,
                scopes=args.scopes,
                keys=ApiKeyRepository(session),
            )
            await session.commit()
    finally:
        await db.dispose()

    print(f"created api key {key.name!r} for org {org.name} (id={org.id})")
    print(f"  id:     {key.id}")
    print(f"  prefix: {key.key_prefix}")
    print(f"  scopes: {key.scopes}")
    print()
    print("  SECRET (shown once — store it now):")
    print(f"  {raw}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_run(_parse_args(sys.argv[1:] if argv is None else argv)))


if __name__ == "__main__":
    raise SystemExit(main())
