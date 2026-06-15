import asyncio
from concurrent.futures import ThreadPoolExecutor

from aiogram.fsm.storage.base import StorageKey
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bot.db.fsm_storage import SQLiteStorage
from bot.db.models import Base, User
from bot.db.repository import UserRepository


def _temporary_session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_fsm_state_survives_storage_recreation(tmp_path, monkeypatch):
    sessions = _temporary_session_factory(tmp_path)
    monkeypatch.setattr("bot.db.repository.get_session", sessions)
    key = StorageKey(bot_id=1, chat_id=2, user_id=3)

    async def exercise_storage():
        first = SQLiteStorage()
        await first.set_state(key, "QuizState:answering")
        await first.set_data(key, {"idx": 7, "score": 5})

        second = SQLiteStorage()
        assert await second.get_state(key) == "QuizState:answering"
        assert await second.get_data(key) == {"idx": 7, "score": 5}

    asyncio.run(exercise_storage())


def test_score_increments_are_atomic(tmp_path, monkeypatch):
    sessions = _temporary_session_factory(tmp_path)
    monkeypatch.setattr("bot.db.repository.get_session", sessions)

    with sessions() as session:
        session.add(User(telegram_id=42, name="Concurrent user"))
        session.commit()

    increments = 20
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: UserRepository.add_to_scores(42, "junior", 1, 1),
                range(increments),
            )
        )

    assert all(result is not None for result in results)
    scores = UserRepository.get_by_telegram_id(42).get_scores("junior")
    assert scores == {"correct": increments, "total": increments}
