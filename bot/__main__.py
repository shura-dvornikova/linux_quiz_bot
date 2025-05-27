import asyncio
import json
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from .config import config

# ─── базовая настройка логирования ──────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

# ─── загрузка вопросов ──────────────────────────────────────────────────────
QUIZ_PATH = Path(__file__).parent / "data" / "quizzes.json"
try:
    with QUIZ_PATH.open(encoding="utf-8") as f:
        QUIZZES: dict[str, list[dict]] = json.load(f)
except FileNotFoundError:
    raise RuntimeError(f"Файл с вопросами не найден: {QUIZ_PATH}")
except json.JSONDecodeError as e:
    raise RuntimeError(f"Ошибка синтаксиса в quizzes.json: {e}") from e

# ─── инициализация бота и диспетчера ────────────────────────────────────────
bot = Bot(
    token=config.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
)
dp = Dispatcher()

# ─── fsm-состояния ──────────────────────────────────────────────────────────
class QuizState(StatesGroup):
    waiting_for_answer = State()

# ─── хэндлеры ───────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(msg: Message) -> None:
    """Стартовое меню: выбор темы."""
    topics = list(QUIZZES.keys())
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=topic, callback_data=f"topic:{topic}")]
            for topic in topics
        ]
    )
    await msg.answer("*Привет!*\nВыбери тему викторины:", reply_markup=kb)


@dp.callback_query(lambda cb: cb.data.startswith("topic:"))
async def choose_topic(cb: CallbackQuery, state: FSMContext) -> None:
    """Пользователь щёлкнул по теме — начинаем викторину."""
    topic = cb.data.split(":", 1)[1]
    await state.update_data(topic=topic, idx=0, score=0)
    await ask_question(cb.message, state)


async def ask_question(msg: Message, state: FSMContext) -> None:
    """Задаём очередной вопрос."""
    data = await state.get_data()
    q = QUIZZES[data["topic"]][data["idx"]]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=opt, callback_data=f"ans:{i}")]
            for i, opt in enumerate(q["options"])
        ]
    )
    await msg.answer(f"*{q['question']}*", reply_markup=kb)
    await state.set_state(QuizState.waiting_for_answer)


@dp.callback_query(QuizState.waiting_for_answer)
async def handle_answer(cb: CallbackQuery, state: FSMContext) -> None:
    """Обрабатываем выбранный вариант ответа."""
    data = await state.get_data()
    q = QUIZZES[data["topic"]][data["idx"]]

    chosen = int(cb.data.split(":", 1)[1])
    correct = chosen == q["correct"]

    # обновляем счёт
    score = data["score"] + int(correct)
    idx = data["idx"] + 1

    await cb.answer("✅ Верно!" if correct else "❌ Неверно", show_alert=True)

    if idx < len(QUIZZES[data["topic"]]):
        # Ещё есть вопросы
        await state.update_data(idx=idx, score=score)
        await ask_question(cb.message, state)
    else:
        # Викторина завершена
        await cb.message.answer(
            f"🏁 Конец!\nПравильных ответов: *{score}* из *{idx}*"
        )
        await state.clear()

# ─── запуск ────────────────────────────────────────────────────────────────
async def main() -> None:
    if not config.bot_token:
        raise RuntimeError("BOT_TOKEN не найден. Добавьте его в .env")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
