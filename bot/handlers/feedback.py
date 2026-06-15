import logging

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode

from bot.config import feedback_channel_id
from bot.states import QuizState
from bot.services.user_service import escape_md

router = Router()


@router.message(Command("feedback"))
async def cmd_feedback(msg: Message, state: FSMContext) -> None:
    """Handle /feedback command."""
    if not feedback_channel_id:
        await msg.answer("Отзывы временно недоступны. Попробуй позже.")
        return

    await msg.answer("✍️ Напиши свой отзыв сообщением, я обязательно прочитаю!")
    await state.set_state(QuizState.waiting_for_feedback)


@router.callback_query(F.data == "feedback")
async def callback_feedback(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle feedback button click."""
    if not feedback_channel_id:
        await cb.answer("Отзывы временно недоступны", show_alert=True)
        return

    await cb.message.answer("📝 Напиши сюда свой отзыв:")
    await state.set_state(QuizState.waiting_for_feedback)
    await cb.answer()


@router.message(QuizState.waiting_for_feedback)
async def handle_feedback(msg: Message, state: FSMContext, bot: Bot) -> None:
    """Process feedback message."""
    feedback_text = (msg.text or "").strip()
    if not feedback_text:
        await msg.answer("Пожалуйста, отправь отзыв текстовым сообщением.")
        return

    if not feedback_channel_id:
        logging.error("FEEDBACK_CHANNEL_ID is not configured")
        await msg.answer("Не удалось отправить отзыв. Попробуй позже.")
        return

    username = msg.from_user.username
    sender = f"@{username}" if username else f"id:{msg.from_user.id}"
    full_name = msg.from_user.full_name
    text = (
        "✉️ *Новый отзыв от @LinuxQuizBot*\n\n"
        f"👤 Пользователь: {escape_md(full_name)}\n"
        f"🔎 Telegram: {escape_md(sender)}\n"
        f"🆔 ID: `{msg.from_user.id}`\n\n"
        f"📝 Сообщение:\n{escape_md(feedback_text)}"
    )

    try:
        await bot.send_message(
            chat_id=int(feedback_channel_id),
            text=text,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except (TelegramAPIError, ValueError) as error:
        logging.exception("Failed to deliver feedback: %s", error)
        await msg.answer("Не удалось отправить отзыв. Попробуй позже.")
        return

    logging.info("Feedback received from %s", sender)
    await msg.answer("Спасибо за отзыв! 💌")
    await state.clear()
