import asyncio
import json
import logging
import random
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BotCommand,
    BotCommandScopeDefault,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from .config import bot_token   # BOT_TOKEN лежит в .env.* и подхватывается в config

# ─── базовое логирование ────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

# ─── читаем вопросы ────────────────────────────────────────────────────────
QUIZ_PATH = Path(__file__).parent / "data" / "quizzes.json"
with QUIZ_PATH.open(encoding="utf-8") as f:
    QUIZZES: dict[str, list[dict]] = json.load(f)

# ─── инициализация бота и диспетчера ───────────────────────────────────────
bot = Bot(
    token=bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
)
dp = Dispatcher()

# ─── на старте задаём /start в меню ─────────────────────────────────────────
async def on_startup(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(
                command="start",
                description="🚀 Начать викторину",
            )
        ],
        scope=BotCommandScopeDefault(),
    )
    logging.info("Меню команд обновлено")

dp.startup.register(on_startup)

# ─── FSM ────────────────────────────────────────────────────────────────────
class QuizState(StatesGroup):
    waiting_for_answer = State()

# ─── /start ─────────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(msg: Message) -> None:
    topics = list(QUIZZES.keys())
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=topic,
                    callback_data=f"topic:{topic}",
                )
            ]
            for topic in topics
        ]
    )
    await msg.answer("*Привет!*\nВыбери тему викторины:", reply_markup=kb)

# ─── выбор темы ────────────────────────────────────────────────────────────
@dp.callback_query(lambda cb: cb.data.startswith("topic:"))
async def choose_topic(cb: CallbackQuery, state: FSMContext) -> None:
    topic = cb.data.split(":", 1)[1]
    await state.update_data(topic=topic, idx=0, score=0, results=[])
    await ask_question(cb.message, state)

# ─── вспомогательный handler для получения file_id фото ────────────────────
@dp.message(lambda m: m.photo)
async def echo_file_id(msg: Message):
    file_id = msg.photo[-1].file_id
    await msg.answer(file_id)
    print(file_id)

# ─── отправка очередного вопроса ────────────────────────────────────────────
async def ask_question(msg: Message, state: FSMContext) -> None:
    data   = await state.get_data()
    topic  = data["topic"]
    idx    = data["idx"]
    total  = len(QUIZZES[topic])
    q      = QUIZZES[topic][idx]

    order = random.sample(range(len(q["options"])), k=len(q["options"]))
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=q["options"][i],
                    callback_data=f"ans:{idx}:{i}",
                )
            ]
            for i in order
        ]
    )

    caption = f"❓_Вопрос {idx + 1} из {total}_\n\n*{q['question']}*"

    try:
        if q.get("file_id"):
            await msg.answer_photo(
                q["file_id"],
                caption=caption,
                reply_markup=kb,
            )
        else:
            await msg.answer(caption, reply_markup=kb)
    except TelegramBadRequest:
        # если file_id битый
        await msg.answer(caption, reply_markup=kb)

    await state.set_state(QuizState.waiting_for_answer)

# ─── ответ на вопрос ───────────────────────────────────────────────────────
@dp.callback_query(QuizState.waiting_for_answer)
async def handle_answer(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    topic = data["topic"]
    cur_idx = data["idx"]

    _, qidx_str, opt_str = cb.data.split(":")
    qidx = int(qidx_str)
    opt  = int(opt_str)

    # клик по старой кнопке
    if qidx != cur_idx:
        await cb.answer()
        return

    q  = QUIZZES[topic][qidx]
    ok = opt == q["correct"]

    data["results"].append({"idx": qidx, "correct": ok})
    data["score"] = data.get("score", 0) + int(ok)
    data["idx"]   = cur_idx + 1
    await state.update_data(**data)

    await cb.answer("✅ Верно!" if ok else "❌ Неверно")

    # ещё есть вопросы
    if data["idx"] < len(QUIZZES[topic]):
        await ask_question(cb.message, state)
        return

    # ── викторина окончена ─────────────────────────────────────────────
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
        f"🏁 Конец!\nПравильных: *{data['score']}* из *{len(data['results'])}*\n\n{report}"
    )
    await state.clear()

    # ── предложение сыграть снова ──────────────────────────────────────
    topics = list(QUIZZES.keys())
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t,
                    callback_data=f"topic:{t}",
                )
            ]
            for t in topics
        ]
    )
    await cb.message.answer(
        "🔄 Хочешь сыграть ещё раз? Выбери тему:",
        reply_markup=kb,
    )

# ─── запуск ────────────────────────────────────────────────────────────────
async def main() -> None:
    if not bot_token:
        raise RuntimeError("BOT_TOKEN не найден")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
