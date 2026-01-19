import logging
import os
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode

from bot.states import QuizState
from bot.services.user_service import escape_md

router = Router()

FEEDBACK_RECEIVER_ID = int(os.getenv("FEEDBACK_RECEIVER_ID", "299416948"))
FEEDBACK_CHANNEL_ID = int(os.getenv("FEEDBACK_CHANNEL_ID", "-1003033348229"))


@router.message(Command("feedback"))
async def cmd_feedback(msg: Message, state: FSMContext) -> None:
    """Handle /feedback command."""
    await msg.answer("✍️ Напиши свой отзыв сообщением, я обязательно прочитаю!")
    await state.set_state(QuizState.waiting_for_feedback)


@router.callback_query(F.data == "feedback")
async def callback_feedback(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle feedback button click."""
    await cb.message.answer("📝 Напиши сюда свой отзыв:")
    await state.set_state(QuizState.waiting_for_feedback)
    await cb.answer()


@router.message(QuizState.waiting_for_feedback)
async def handle_feedback(msg: Message, state: FSMContext, bot: Bot) -> None:
    """Process feedback message."""
    try:
        username = msg.from_user.username
        if username:
            safe_username = f"@{username}"
        else:
            safe_username = f"id:{msg.from_user.id}"

        feedback_text = msg.text or "(пустое сообщение)"

        text = (
            f"✉️ *Новый отзыв*\n\n"
            f"👤 От: {escape_md(safe_username)}\n"
            f"📝 Сообщение:\n{escape_md(feedback_text)}"
        )

        # Send to feedback channel
        await bot.send_message(
            chat_id=FEEDBACK_CHANNEL_ID, text=text, parse_mode=ParseMode.MARKDOWN_V2
        )
        logging.info(f"Feedback received from {safe_username}")

    except Exception as e:
        logging.warning(f"Failed to send feedback to channel: {e}")

    await msg.answer("Спасибо за отзыв! 💌")
    await state.clear()
