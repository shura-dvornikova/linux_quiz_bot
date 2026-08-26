import html
import logging
import re
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from bot.db.models import User
from bot.db.repository import UserRepository


def escape_md(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    return re.sub(
        r"([_*\[\]()~`>#+\-=|{}.!\\])",
        r"\\\1",
        str(text),
    )


def escape_html(text: str) -> str:
    """Escape text for Telegram HTML."""
    return html.escape(str(text))


class UserService:
    """Service for user operations."""

    PROGRESS_TOTAL = 200

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
        telegram_id: int,
        level: str,
        correct: int,
        total: int,
    ) -> Optional[User]:
        """Add quiz results to user's scores."""
        return UserRepository.add_to_scores(
            telegram_id,
            level,
            correct,
            total,
        )

    @staticmethod
    def get_scores_text(telegram_id: int) -> str:
        """
        Get plain-text progress.

        Progress means the number of CORRECT answers
        out of the total 200 questions for the level.
        """
        user = UserRepository.get_by_telegram_id(telegram_id)

        if not user:
            return "Нет данных"

        scores = user.get_all_scores()

        lines = []

        level_names = {
            "junior": "Junior",
            "middle": "Middle",
            "senior": "Senior",
        }

        for level in ("junior", "middle", "senior"):
            correct = min(
                scores[level]["correct"],
                UserService.PROGRESS_TOTAL,
            )

            percent = correct / UserService.PROGRESS_TOTAL * 100

            if percent.is_integer():
                percent_text = str(int(percent))
            else:
                percent_text = f"{percent:.1f}"

            lines.append(
                f"{level_names[level]}: "
                f"{correct} из {UserService.PROGRESS_TOTAL} "
                f"({percent_text}%)"
            )

        return "\n".join(lines)

    @staticmethod
    def get_scores_text_escaped(telegram_id: int) -> str:
        """Get progress formatted for MarkdownV2."""
        user = UserRepository.get_by_telegram_id(telegram_id)

        if not user:
            return "Нет данных"

        scores = user.get_all_scores()

        level_names = {
            "junior": "Junior",
            "middle": "Middle",
            "senior": "Senior",
        }

        lines = []

        for level in ("junior", "middle", "senior"):
            correct = min(
                scores[level]["correct"],
                UserService.PROGRESS_TOTAL,
            )

            percent = correct / UserService.PROGRESS_TOTAL * 100

            if percent.is_integer():
                percent_text = str(int(percent))
            else:
                percent_text = f"{percent:.1f}"

            lines.append(
                f"*{escape_md(level_names[level])}:* "
                f"{correct} из {UserService.PROGRESS_TOTAL} "
                f"\\({escape_md(percent_text)}%\\)"
            )

        return "\n".join(lines)

    @staticmethod
    def get_progress_html(telegram_id: int) -> str:
        """
        Build the progress message.

        Uses HTML instead of MarkdownV2 so that spaces
        and line breaks are displayed correctly.
        """
        user = UserRepository.get_by_telegram_id(telegram_id)

        if not user:
            return "📊 <b>Мой прогресс</b>\n\nНет данных"

        scores = user.get_all_scores()

        level_info = [
            ("🟢", "Junior", "junior"),
            ("🟡", "Middle", "middle"),
            ("🔴", "Senior", "senior"),
        ]

        lines = [
            "📊 <b>Мой прогресс</b>",
            "",
        ]

        for emoji, name, level in level_info:
            # ВАЖНО:
            # здесь показываем именно количество правильных ответов,
            # а не количество пройденных вопросов.
            correct = min(
                scores[level]["correct"],
                UserService.PROGRESS_TOTAL,
            )

            percent = correct / UserService.PROGRESS_TOTAL * 100

            if percent.is_integer():
                percent_text = str(int(percent))
            else:
                percent_text = f"{percent:.1f}"

            lines.append(
                f"{emoji} <b>{name}:</b> "
                f"{correct} из {UserService.PROGRESS_TOTAL} "
                f"({percent_text}%)"
            )

        return "\n".join(lines)

    @staticmethod
    async def update_pinned_score(
        bot: Bot,
        telegram_id: int,
        chat_id: int,
    ) -> None:
        """Update or create the pinned progress message."""
        user = UserRepository.get_by_telegram_id(telegram_id)

        if not user:
            return

        text = UserService.get_progress_html(telegram_id)

        try:
            if user.pinned_message_id:
                # Try to edit existing pinned message.
                try:
                    await bot.edit_message_text(
                        text=text,
                        chat_id=chat_id,
                        message_id=user.pinned_message_id,
                        parse_mode="HTML",
                    )
                    return
                except TelegramBadRequest:
                    # Message was deleted or cannot be edited.
                    pass

            # Create a new progress message.
            msg = await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
            )

            # Try to pin it.
            try:
                await bot.pin_chat_message(
                    chat_id=chat_id,
                    message_id=msg.message_id,
                    disable_notification=True,
                )
            except TelegramBadRequest:
                # Pinning may be unavailable in this chat.
                pass

            UserRepository.update_pinned_message(
                telegram_id,
                msg.message_id,
            )

        except TelegramBadRequest as e:
            logging.warning(
                "Failed to update pinned progress message: %s",
                e,
            )