from aiogram import Router

from bot.handlers.start import router as start_router
from bot.handlers.quiz import router as quiz_router
from bot.handlers.feedback import router as feedback_router


def setup_routers() -> Router:
    """Setup and return the main router with all sub-routers."""
    router = Router()
    router.include_router(start_router)
    router.include_router(quiz_router)
    router.include_router(feedback_router)
    return router


__all__ = ["setup_routers"]
