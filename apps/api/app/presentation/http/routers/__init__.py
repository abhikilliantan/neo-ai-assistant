from app.presentation.http.routers.auth import router as auth_router
from app.presentation.http.routers.system import router as system_router

__all__ = ["auth_router", "system_router"]
