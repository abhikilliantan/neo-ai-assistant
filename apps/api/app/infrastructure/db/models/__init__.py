"""ORM models. Importing this package registers all tables on Base.metadata."""

from app.infrastructure.db.models.chat import MESSAGE_ROLES, Conversation, Message
from app.infrastructure.db.models.datasets import (
    COLUMN_DATA_TYPES,
    COLUMN_SEMANTIC_ROLES,
    DATASET_STATUSES,
    Dataset,
    DatasetColumn,
    DatasetRow,
)
from app.infrastructure.db.models.documents import (
    DOCUMENT_STATUSES,
    Document,
    DocumentChunk,
)
from app.infrastructure.db.models.hierarchy import Company, Department, Project
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
    "COLUMN_DATA_TYPES",
    "COLUMN_SEMANTIC_ROLES",
    "DATASET_STATUSES",
    "DOCUMENT_STATUSES",
    "EMBEDDING_DIMENSION",
    "MEMBERSHIP_STATUSES",
    "MEMORY_KINDS",
    "MESSAGE_ROLES",
    "ApiKey",
    "Company",
    "Conversation",
    "Dataset",
    "DatasetColumn",
    "DatasetRow",
    "Department",
    "Document",
    "DocumentChunk",
    "Membership",
    "Memory",
    "Message",
    "Organization",
    "Permission",
    "Project",
    "Role",
    "RolePermission",
    "Session",
    "User",
    "UserPreference",
    "Workflow",
]
