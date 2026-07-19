"""ORM models. Importing this package registers all tables on Base.metadata."""

from app.infrastructure.db.models.chat import MESSAGE_ROLES, Conversation, Message
from app.infrastructure.db.models.identity import Session, User
from app.infrastructure.db.models.rbac import Permission, Role, RolePermission
from app.infrastructure.db.models.tenancy import (
    MEMBERSHIP_STATUSES,
    ApiKey,
    Membership,
    Organization,
)

__all__ = [
    "MEMBERSHIP_STATUSES",
    "MESSAGE_ROLES",
    "ApiKey",
    "Conversation",
    "Membership",
    "Message",
    "Organization",
    "Permission",
    "Role",
    "RolePermission",
    "Session",
    "User",
]
