import asyncio
import json
import logging
import os
import random
import re
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
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    BotCommandScopeDefault,
)


def escape_md(text: str) -> str:
    """
    Экранирует спецсимволы MarkdownV2 для Telegram.
    """
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)


ENV = os.getenv("ENV", "dev").lower()
FEEDBACK_RECEIVER_ID = 299416948
FEEDBACK_CHANNEL_ID = -1003033348229
bot_token = os.getenv("BOT_TOKEN")
if not bot_token:
    raise RuntimeError("❌ Не задан BOT_TOKEN")

LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
logging.basicConfig(level=LOG_LEVEL)


QUIZ_PATH = Path(__file__).parent / "data" / "quizzes.json"
QUIZZES: dict[str, list[dict]]
with QUIZ_PATH.open(encoding="utf-8") as f:
    QUIZZES = json.load(f)


bot = Bot(
    token=bot_token, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
)

dp = Dispatcher()


async def on_startup(bot: Bot) -> None:
    await bot.set_my_commands(
        commands=[
            BotCommand(command="start", description="🦄 Начать викторину заново"),
            BotCommand(command="feedback", description="✉️ Оставить фидбек"),
        ],
        scope=BotCommandScopeDefault(),
    )
    logging.info("Меню команд обновлено")


dp.startup.register(on_startup)


class QuizState(StatesGroup):
    waiting_for_answer = State()
    waiting_for_feedback = State()  # 👈 добавили новое состояние


@dp.message(Command("start"))
async def cmd_start(msg: Message) -> None:
    topics = list(QUIZZES.keys())
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=topic, callback_data=f"topic:{topic}")]
            for topic in topics
        ]
    )
    await msg.answer(r"\*Привет\!\*\nВыбери тему викторины:", reply_markup=kb)



@dp.message(Command("feedback"))
async def cmd_feedback(msg: Message, state: FSMContext) -> None:
    await msg.answer("✍️ Напиши свой фидбек сообщением, я обязательно прочитаю!")
    await state.set_state(QuizState.waiting_for_feedback)


@dp.callback_query(lambda cb: cb.data.startswith("topic:"))
async def choose_topic(cb: CallbackQuery, state: FSMContext) -> None:
    topic = cb.data.split(":", 1)[1]
    await state.update_data(topic=topic, idx=0, score=0, results=[])
    await ask_question(cb.message, state)


@dp.message(lambda m: m.photo)
async def echo_file_id(msg: Message):
    await msg.answer(msg.photo[-1].file_id)


async def ask_question(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    topic = data["topic"]
    idx = data["idx"]

    if idx >= len(QUIZZES[topic]):
        await msg.answer("❗ Нет больше вопросов. Нажми /start.")
        await state.clear()
        return

    q = QUIZZES[topic][idx]
    order = random.sample(range(len(q["options"])), len(q["options"]))
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=q["options"][i], callback_data=f"ans:{idx}:{i}")]
            for i in order
        ]
    )

    caption = (
        f"❓_Вопрос {idx + 1} из {len(QUIZZES[topic])}_\n\n"
        f"*{escape_md(q['question'].splitlines()[0])}*\n"
        + "\n".join(escape_md(line) for line in q["question"].splitlines()[1:])
    )
    try:
        if q.get("file_id"):
            await msg.answer_photo(q["file_id"], caption=caption, reply_markup=kb)
        else:
            await msg.answer(caption, reply_markup=kb)
    except TelegramBadRequest as e:
        logging.warning(f"Ошибка при отправке: {e}")
        await msg.answer(caption[:400], reply_markup=kb)

    await state.set_state(QuizState.waiting_for_answer)


@dp.callback_query(QuizState.waiting_for_answer)
async def handle_answer(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    topic = data["topic"]

    try:
        _, qidx_str, opt_str = cb.data.split(":")
        qidx = int(qidx_str)
        opt = int(opt_str)
    except Exception as e:
        logging.error(f"Неверный формат callback: {cb.data} — {e}")
        await cb.answer("❌ Ошибка обработки ответа")
        return
    if qidx != data["idx"]:
        await cb.answer("⚠️ Этот вопрос уже пройден", show_alert=True)
        return

    q = QUIZZES[topic][qidx]
    correct = q["correct"]
    ok = opt == correct

    data["results"].append({"idx": qidx, "correct": ok})
    data["score"] += int(ok)
    data["idx"] += 1
    await state.update_data(**data)

    await cb.answer("✅ Верно!" if ok else "❌ Неверно", show_alert=False)

    if data["idx"] < len(QUIZZES[topic]):
        await ask_question(cb.message, state)
        return

    lines = []
    for i, item in enumerate(data["results"], start=1):
        q_obj = QUIZZES[topic][item["idx"]]
        mark = "✅" if item["correct"] else "❌"
        right = q_obj["options"][int(q_obj["correct"])]
        lines.append(
            f"{mark} *Вопрос {i}:* {escape_md(q_obj['question'])}\n"
            f" *Правильный ответ:* _{escape_md(right)}_"
        )

    topic_name = data["topic"]

    await cb.message.answer(
        f"🏁 Конец!\n"
        f"📚 Тема: *{topic_name}*\n"
        f"Правильных: *{data['score']}* из *{len(data['results'])}*\n\n"
        + "\n\n".join(lines)
    )
    await state.clear()

    topics = list(QUIZZES.keys())
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=f"topic:{t}")] for t in topics
        ]
    )
    await cb.message.answer("🔄 Хочешь сыграть ещё раз? Выбери тему:", reply_markup=kb)


@dp.callback_query()
async def unknown_callback(cb: CallbackQuery):
    await cb.answer(
        "⚠️ Ответ устарел или сессия завершена. Нажми /start", show_alert=True
    )


@dp.callback_query(lambda cb: cb.data == "feedback")
async def handle_feedback_request(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("📝 Напиши сюда свой фидбек:")
    await state.set_state(QuizState.waiting_for_feedback)
    await cb.answer()


@dp.message(QuizState.waiting_for_feedback)
async def handle_feedback(msg: Message, state: FSMContext) -> None:
    try:
        username = msg.from_user.username
        if username:
            safe_username = "@" + username.replace("_", "\\_")
        else:
            safe_username = f"[id {msg.from_user.id}]"

        text = (
            f"✉️ *Новый фидбек*\n"
            f"👤 От: {safe_username}\n"
            f"📝 Сообщение:\n{msg.text}"
        )

        await bot.send_message(
            chat_id=FEEDBACK_CHANNEL_ID,
            text=escape_md(text),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as e:
        logging.warning(f"❌ Не удалось отправить фидбек в канал: {e}")
    await msg.answer("Спасибо за фидбек! 💌")
    await state.clear()


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
