import asyncio
import json
import logging
import random
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
from aiogram.exceptions import TelegramBadRequest   # ← для try/except

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
    """Пользователь выбрал тему — начинаем викторину."""
    topic = cb.data.split(":", 1)[1]
    await state.update_data(topic=topic, idx=0, score=0, results=[])
    await ask_question(cb.message, state)


@dp.message(lambda m: m.photo)  # утилитарный хэндлер — получить file_id
async def echo_file_id(msg: Message):
    file_id = msg.photo[-1].file_id
    await msg.answer(file_id)
    print(file_id)


# ─── вывод очередного вопроса ───────────────────────────────────────────────
async def ask_question(msg: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    topic  = data["topic"]
    idx    = data["idx"]                     # номер текущего вопроса
    total  = len(QUIZZES[topic])
    q      = QUIZZES[topic][idx]

    # случайный порядок ответов
    order = list(range(len(q["options"])))
    random.shuffle(order)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=q["options"][i],
                    callback_data=f"ans:{idx}:{i}",  # ans:QIDX:OPTIDX
                )
            ]
            for i in order
        ]
    )

    caption = f"❓_Вопрос {idx + 1} из {total}_\n\n*{q['question']}*"

    # пробуем отправить фото, если оно задано
    if q.get("file_id"):
        try:
            await msg.answer_photo(
                q["file_id"],
                caption=caption,
                reply_markup=kb,
                parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramBadRequest as err:
            logging.warning(
                "Не удалось отправить фото вопроса %s (%s) — %s",
                idx + 1,
                q.get("file_id"),
                err,
            )
            await msg.answer(caption, reply_markup=kb)
    else:
        await msg.answer(caption, reply_markup=kb)

    await state.set_state(QuizState.waiting_for_answer)


# ─── обработка ответа ───────────────────────────────────────────────────────
@dp.callback_query(QuizState.waiting_for_answer)
async def handle_answer(cb: CallbackQuery, state: FSMContext) -> None:
    data   = await state.get_data()
    topic  = data["topic"]
    idx    = data["idx"]          # номер актуального вопроса

    # callback_data = "ans:q_idx:opt_idx"
    _, q_idx_str, opt_idx_str = cb.data.split(":")
    q_idx  = int(q_idx_str)
    chosen = int(opt_idx_str)

    # нажатие на старую кнопку — игнорируем
    if q_idx != idx:
        await cb.answer()  # молча
        return

    q       = QUIZZES[topic][idx]
    correct = chosen == q["correct"]

    data["results"].append({"idx": idx, "correct": correct})
    score    = data["score"] + int(correct)
    next_idx = idx + 1

    await cb.answer("✅ Верно!" if correct else "❌ Неверно")

    if next_idx < len(QUIZZES[topic]):
        await state.update_data(idx=next_idx, score=score, results=data["results"])
        await ask_question(cb.message, state)
    else:
        # итоговый отчёт
        lines = []
        for i, item in enumerate(data["results"], start=1):
            q_obj = QUIZZES[topic][item["idx"]]
            mark  = "✅" if item["correct"] else "❌"
            right = q_obj["options"][q_obj["correct"]]
            lines.append(
                f"{mark} *Вопрос {i}:* {q_obj['question']}\n *Правильный ответ:* _{right}_"
            )

        report = "\n\n".join(lines)
        await cb.message.answer(
            f"🏁 Конец!\nПравильных ответов: *{score}* из *{len(data['results'])}*\n\n{report}"
        )
        await state.clear()

        # предложение сыграть ещё
        topics = list(QUIZZES.keys())
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t, callback_data=f"topic:{t}")] for t in topics
            ]
        )
        await cb.message.answer("🔄 Хочешь сыграть ещё раз? Выбери тему:", reply_markup=kb)


# ─── запуск ────────────────────────────────────────────────────────────────
async def main() -> None:
    if not config.bot_token:
        raise RuntimeError("BOT_TOKEN не найден. Добавьте его в .env")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
