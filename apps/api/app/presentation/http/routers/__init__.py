from app.presentation.http.routers.agents import router as agents_router
from app.presentation.http.routers.auth import router as auth_router
from app.presentation.http.routers.chat import router as chat_router
from app.presentation.http.routers.conversations import router as conversations_router
from app.presentation.http.routers.documents import router as documents_router
from app.presentation.http.routers.memories import router as memories_router
from app.presentation.http.routers.system import router as system_router

__all__ = [
    "agents_router",
    "auth_router",
    "chat_router",
    "conversations_router",
    "documents_router",
    "memories_router",
    "system_router",
]
