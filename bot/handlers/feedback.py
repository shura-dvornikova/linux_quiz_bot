import logging

from aiogram import Router, F, Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.config import feedback_channel_id, get_feedback_chat_id
from bot.states import QuizState

router = Router()


def _feedback_error_message(error: Exception) -> str:
    """Return an actionable message for feedback delivery failures."""
    description = str(error).lower()
    if isinstance(error, TelegramForbiddenError):
        return "Бот не имеет доступа к каналу отзывов. Добавь его администратором."
    if isinstance(error, TelegramNotFound) or "chat not found" in description:
        return "Канал отзывов не найден. Проверь FEEDBACK_CHANNEL_ID."
    if isinstance(error, TelegramBadRequest) and (
        "not enough rights" in description
        or "need administrator rights" in description
        or "message can't be sent" in description
    ):
        return (
            "Боту не разрешено публиковать в канале отзывов. Выдай право Post Messages."
        )
    if isinstance(error, TelegramNetworkError):
        return "Telegram временно недоступен. Попробуй отправить отзыв ещё раз."
    if isinstance(error, ValueError):
        return "Неверный FEEDBACK_CHANNEL_ID. Нужен ID вида -100... или @username."
    return "Не удалось отправить отзыв. Ошибка записана в журнал бота."


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
        "✉️ Новый отзыв от @LinuxQuizBot\n\n"
        f"👤 Пользователь: {full_name}\n"
        f"🔎 Telegram: {sender}\n"
        f"🆔 ID: {msg.from_user.id}\n\n"
        f"📝 Сообщение:\n{feedback_text}"
    )

    try:
        await bot.send_message(
            chat_id=get_feedback_chat_id(feedback_channel_id),
            text=text,
            parse_mode=None,
        )
    except (TelegramAPIError, ValueError) as error:
        logging.exception(
            "Failed to deliver feedback to %r: %s",
            feedback_channel_id,
            error,
        )
        await msg.answer(_feedback_error_message(error))
        return

    logging.info("Feedback received from %s", sender)
    await msg.answer("Спасибо за отзыв! 💌")
    await state.clear()
