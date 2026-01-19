from typing import Optional
from bot.db.models import User, get_session


class UserRepository:
    """Repository for user data operations."""

    @staticmethod
    def get_by_telegram_id(telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        with get_session() as session:
            return session.query(User).filter(User.telegram_id == telegram_id).first()

    @staticmethod
    def create(telegram_id: int, name: str) -> User:
        """Create a new user."""
        with get_session() as session:
            user = User(telegram_id=telegram_id, name=name)
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    @staticmethod
    def get_or_create(telegram_id: int, name: str) -> tuple[User, bool]:
        """Get existing user or create new one. Returns (user, created)."""
        user = UserRepository.get_by_telegram_id(telegram_id)
        if user:
            return user, False
        return UserRepository.create(telegram_id, name), True

    @staticmethod
    def update_name(telegram_id: int, name: str) -> Optional[User]:
        """Update user's name."""
        with get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.name = name
                session.commit()
                session.refresh(user)
            return user

    @staticmethod
    def update_level(telegram_id: int, level: str) -> Optional[User]:
        """Update user's selected level."""
        with get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.level = level
                session.commit()
                session.refresh(user)
            return user

    @staticmethod
    def update_scores(
        telegram_id: int, level: str, correct: int, total: int
    ) -> Optional[User]:
        """Update user's scores for a specific level."""
        with get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.set_scores(level, correct, total)
                session.commit()
                session.refresh(user)
            return user

    @staticmethod
    def add_to_scores(
        telegram_id: int, level: str, correct_delta: int, total_delta: int
    ) -> Optional[User]:
        """Add to user's scores for a specific level."""
        with get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                current = user.get_scores(level)
                user.set_scores(
                    level,
                    current["correct"] + correct_delta,
                    current["total"] + total_delta,
                )
                session.commit()
                session.refresh(user)
            return user

    @staticmethod
    def update_pinned_message(telegram_id: int, message_id: int) -> Optional[User]:
        """Update user's pinned message ID."""
        with get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.pinned_message_id = message_id
                session.commit()
                session.refresh(user)
            return user

    @staticmethod
    def get_pinned_message_id(telegram_id: int) -> Optional[int]:
        """Get user's pinned message ID."""
        user = UserRepository.get_by_telegram_id(telegram_id)
        return user.pinned_message_id if user else None
