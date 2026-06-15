import json
from typing import Optional

from sqlalchemy import Integer, cast, func, update
from sqlalchemy.dialects.sqlite import insert

from bot.db.models import FSMRecord, User, VALID_LEVELS, get_session


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
        """Atomically add to a user's scores for a specific level."""
        if level not in VALID_LEVELS:
            raise ValueError(f"Unsupported quiz level: {level}")

        score_column = getattr(User, f"scores_{level}")
        correct = func.coalesce(
            cast(func.json_extract(score_column, "$.correct"), Integer), 0
        )
        total = func.coalesce(
            cast(func.json_extract(score_column, "$.total"), Integer), 0
        )

        with get_session() as session:
            result = session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(
                    {
                        score_column: func.json_object(
                            "correct",
                            correct + correct_delta,
                            "total",
                            total + total_delta,
                        )
                    }
                )
            )
            if result.rowcount == 0:
                session.rollback()
                return None

            session.commit()
            return session.query(User).filter(User.telegram_id == telegram_id).first()

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


class FSMRepository:
    """Persistence operations used by the aiogram FSM storage adapter."""

    @staticmethod
    def get(key: str) -> tuple[Optional[str], dict]:
        with get_session() as session:
            record = session.get(FSMRecord, key)
            if not record:
                return None, {}
            return record.state, json.loads(record.data)

    @staticmethod
    def set_state(key: str, state: Optional[str]) -> None:
        with get_session() as session:
            statement = insert(FSMRecord).values(key=key, state=state, data="{}")
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=[FSMRecord.key], set_={"state": state}
                )
            )
            session.commit()

    @staticmethod
    def set_data(key: str, data: dict) -> None:
        encoded = json.dumps(data, ensure_ascii=False)
        with get_session() as session:
            statement = insert(FSMRecord).values(key=key, state=None, data=encoded)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=[FSMRecord.key], set_={"data": encoded}
                )
            )
            session.commit()
