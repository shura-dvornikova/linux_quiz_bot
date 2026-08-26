import re
from typing import Optional
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from bot.db.repository import UserRepository
from bot.db.models import User


def escape_md(text: str) -> str:
    """Escape special characters for MarkdownV2."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)


class UserService:
    """Service for user operations."""

    @staticmethod
    def get_user(telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        return UserRepository.get_by_telegram_id(telegram_id)

    @staticmethod
    def create_user(telegram_id: int, name: str) -> User:
        """Create a new user."""
        return UserRepository.create(telegram_id, name)

    @staticmethod
    def update_name(telegram_id: int, name: str) -> Optional[User]:
        """Update user's name."""
        return UserRepository.update_name(telegram_id, name)

    @staticmethod
    def set_level(telegram_id: int, level: str) -> Optional[User]:
        """Set user's difficulty level."""
        return UserRepository.update_level(telegram_id, level)

    @staticmethod
    def add_quiz_result(
        telegram_id: int, level: str, correct: int, total: int
    ) -> Optional[User]:
        """Add quiz results to user's scores."""
        return UserRepository.add_to_scores(telegram_id, level, correct, total)

    @staticmethod
    def get_scores_text(telegram_id: int) -> str:
        """Get formatted scores text for display."""
        user = UserRepository.get_by_telegram_id(telegram_id)
        if not user:
            return "Нет данных"

        scores = user.get_all_scores()
        return (
            f"Junior: {scores['junior']['correct']} из {scores['junior']['total']}\n"
            f"Middle: {scores['middle']['correct']} из {scores['middle']['total']}\n"
            f"Senior: {scores['senior']['correct']} из {scores['senior']['total']}"
        )

    @staticmethod
    def get_scores_text_escaped(telegram_id: int) -> str:
        """Get formatted scores text with MarkdownV2 escaping."""
        user = UserRepository.get_by_telegram_id(telegram_id)
        if not user:
            return "Нет данных"

        scores = user.get_all_scores()
        lines = [
            f"*Junior:* {scores['junior']['correct']} из {scores['junior']['total']}",
            f"*Middle:* {scores['middle']['correct']} из {scores['middle']['total']}",
            f"*Senior:* {scores['senior']['correct']} из {scores['senior']['total']}",
        ]
        return "\n".join(lines)

    @staticmethod
    async def update_pinned_score(bot: Bot, telegram_id: int, chat_id: int) -> None:
        """Update or create pinned score message."""
        user = UserRepository.get_by_telegram_id(telegram_id)
        if not user:
            return

        scores = user.get_all_scores()
        text = (
            f"📊 *{escape_md(user.name)}*\n\n"
            f"*Junior:* {scores['junior']['correct']} из {scores['junior']['total']}\n"
            f"*Middle:* {scores['middle']['correct']} из {scores['middle']['total']}\n"
            f"*Senior:* {scores['senior']['correct']} из {scores['senior']['total']}"
        )

        try:
            if user.pinned_message_id:
                # Try to edit existing message
                try:
                    await bot.edit_message_text(
                        text=text,
                        chat_id=chat_id,
                        message_id=user.pinned_message_id,
                        parse_mode="MarkdownV2",
                    )
                    return
                except TelegramBadRequest:
                    # Message was deleted or can't be edited, create new one
                    pass

            # Create and pin new message
            msg = await bot.send_message(chat_id, text, parse_mode="MarkdownV2")
            try:
                await bot.pin_chat_message(
                    chat_id=chat_id,
                    message_id=msg.message_id,
                    disable_notification=True,
                )
            except TelegramBadRequest:
                # Can't pin in this chat type, that's ok
                pass
            UserRepository.update_pinned_message(telegram_id, msg.message_id)

        except TelegramBadRequest as e:
            # Log but don't fail
            import logging

            logging.warning(f"Failed to update pinned score: {e}")
