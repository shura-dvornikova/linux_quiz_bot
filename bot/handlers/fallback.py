from aiogram import Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query()
async def unknown_callback(cb: CallbackQuery) -> None:
    """Handle callbacks not claimed by a feature router."""
    await cb.answer(
        "⚠️ Действие устарело или сессия завершена. Нажми /start", show_alert=True
    )
