import json
from typing import Any, Optional

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey

from bot.db.repository import FSMRepository


class SQLiteStorage(BaseStorage):
    """Persist aiogram FSM state in the application's SQLite database."""

    @staticmethod
    def _key(key: StorageKey) -> str:
        return json.dumps(
            [
                key.bot_id,
                key.chat_id,
                key.user_id,
                key.thread_id,
                key.business_connection_id,
                key.destiny,
            ],
            separators=(",", ":"),
        )

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        value = state.state if isinstance(state, State) else state
        FSMRepository.set_state(self._key(key), value)

    async def get_state(self, key: StorageKey) -> Optional[str]:
        state, _ = FSMRepository.get(self._key(key))
        return state

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        FSMRepository.set_data(self._key(key), data.copy())

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        _, data = FSMRepository.get(self._key(key))
        return data.copy()

    async def close(self) -> None:
        pass
