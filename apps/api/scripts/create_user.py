"""Admin provisioning CLI (Neo 1.0 R6).

Creates a user + organization + owner membership DIRECTLY, bypassing the HTTP
`POST /register` route. This is the pilot's onboarding path once public
registration is gated off (`registration_enabled=False`): it runs on the
privileged `neo` system session, issues no tokens, opens no HTTP surface, and is
NOT subject to the registration flag.

It reuses the SAME building block the route uses — `SystemRepository.register_bootstrap`
— and the SAME argon2 hashing (`hash_password`), so there is no new crypto and no
new cross-tenant surface, just a different entry point. The `owner` role it
assigns is seeded by migrations (`d68d0f6a4fa8_identity_and_tenancy`).

Run inside the api container:  make create-user EMAIL=a@b.com PASSWORD=... ORG="Acme"
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.config import get_settings
from app.infrastructure.db.models import Membership, Organization, User
from app.infrastructure.db.repositories import SystemRepository
from app.infrastructure.db.session import build_system_database
from app.infrastructure.security import hash_password, normalize_email
from app.shared.exceptions.auth import EmailAlreadyRegisteredError

_MIN_PASSWORD_LEN = 8  # mirrors RegisterRequest (schemas/auth.py) — never weaker than the API


async def provision_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    org_name: str | None = None,
) -> tuple[User, Organization, Membership]:
    """Create user + org + owner membership on the given (privileged) session.

    Does NOT commit — the caller owns the transaction. Raises
    `EmailAlreadyRegisteredError` if the email already exists (pre-check) or races
    a concurrent insert (register_bootstrap's IntegrityError guard).
    """
    system = SystemRepository(session)
    email_norm = normalize_email(email)
    if await system.find_user_by_email(email_norm) is not None:
        raise EmailAlreadyRegisteredError(email_norm)
    # Same default-org derivation as the register use case (auth.py:104).
    name = org_name or f"{email_norm.split('@')[0]}'s workspace"
    return await system.register_bootstrap(
        email_normalized=email_norm,
        password_hash=hash_password(password),
        org_name=name,
        role_name="owner",
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="create_user",
        description="Provision a pilot user + organization + owner membership.",
    )
    parser.add_argument("--email", required=True, help="user email address")
    # ponytail: password on the CLI is visible in the process list — acceptable for
    # an operator-run pilot provisioning tool; move to a prompt/stdin if that ceiling matters.
    parser.add_argument("--password", required=True, help="initial password (>= 8 chars)")
    parser.add_argument(
        "--org", default=None, help='organization name (default: "<local-part>\'s workspace")'
    )
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    if len(args.password) < _MIN_PASSWORD_LEN:
        print(f"error: password must be at least {_MIN_PASSWORD_LEN} characters", file=sys.stderr)
        return 1
    db = build_system_database(get_settings())
    try:
        async with db.sessionmaker() as session:
            try:
                user, org, _ = await provision_user(
                    session, email=args.email, password=args.password, org_name=args.org
                )
            except EmailAlreadyRegisteredError as e:
                print(f"error: email {e} is already registered", file=sys.stderr)
                return 1
            await session.commit()
    finally:
        await db.dispose()
    print(f"created user {user.email} (id={user.id}) + org {org.name} (id={org.id}), role 'owner'")
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_run(_parse_args(sys.argv[1:] if argv is None else argv)))


if __name__ == "__main__":
    raise SystemExit(main())
