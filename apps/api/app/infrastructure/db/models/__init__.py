"""ORM models. Importing this package registers all tables on Base.metadata."""

from app.infrastructure.db.models.chat import MESSAGE_ROLES, Conversation, Message
from app.infrastructure.db.models.documents import (
    DOCUMENT_STATUSES,
    Document,
    DocumentChunk,
)
from app.infrastructure.db.models.identity import Session, User
from app.infrastructure.db.models.memory import (
    EMBEDDING_DIMENSION,
    MEMORY_KINDS,
    Memory,
    UserPreference,
)
from app.infrastructure.db.models.rbac import Permission, Role, RolePermission
from app.infrastructure.db.models.tenancy import (
    MEMBERSHIP_STATUSES,
    ApiKey,
    Membership,
    Organization,
)
from app.infrastructure.db.models.workflows import Workflow

__all__ = [
    "DOCUMENT_STATUSES",
    "EMBEDDING_DIMENSION",
    "MEMBERSHIP_STATUSES",
    "MEMORY_KINDS",
    "MESSAGE_ROLES",
    "ApiKey",
    "Conversation",
    "Document",
    "DocumentChunk",
    "Membership",
    "Memory",
    "Message",
    "Organization",
    "Permission",
    "Role",
    "RolePermission",
    "Session",
    "User",
    "UserPreference",
    "Workflow",
]
