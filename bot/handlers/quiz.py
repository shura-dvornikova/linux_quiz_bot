import asyncio
import logging
import weakref

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.exceptions import TelegramBadRequest

from bot.states import QuizState
from bot.keyboards import build_answers_keyboard, build_restart_keyboard
from bot.keyboards.builders import get_topic_name, get_level_name
from bot.services.quiz_service import QuizService
from bot.services.user_service import UserService, escape_md

router = Router()
_answer_locks: weakref.WeakValueDictionary[tuple[int, int], asyncio.Lock] = (
    weakref.WeakValueDictionary()
)


def _get_answer_lock(chat_id: int, user_id: int) -> asyncio.Lock:
    """Return the lock that serializes answers from one user in one chat."""
    key = (chat_id, user_id)
    lock = _answer_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _answer_locks[key] = lock
    return lock


def _build_answered_keyboard(
    keyboard: InlineKeyboardMarkup | None,
    selected_callback_data: str,
    is_correct: bool,
) -> InlineKeyboardMarkup | None:
    """Mark the selected answer while preserving the original keyboard order."""
    if keyboard is None:
        return None

    mark = "✅" if is_correct else "❌"
    rows = []
    for row in keyboard.inline_keyboard:
        rows.append(
            [
                (
                    button.model_copy(update={"text": f"{mark} {button.text}"[:64]})
                    if button.callback_data == selected_callback_data
                    else button
                )
                for button in row
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(QuizState.selecting_topic, F.data.startswith("topic:"))
async def choose_topic(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle topic selection and start quiz."""
    topic = cb.data.split(":", 1)[1]
    data = await state.get_data()
    level = data.get("level", "junior")

    # Check if there are questions for this topic/level
    question_count = QuizService.get_question_count(topic, level)
    if question_count == 0:
        await cb.answer(
            f"Нет вопросов для уровня {get_level_name(level)} в этой теме",
            show_alert=True,
        )
        return

    # Initialize quiz state
    await state.update_data(topic=topic, level=level, idx=0, score=0, results=[])

    await cb.message.edit_text(
        f"📚 *{escape_md(get_topic_name(topic))}*\n"
        f"Уровень: *{get_level_name(level)}*\n"
        f"Вопросов: {question_count}\n\n"
        "Начинаем\\!",
        parse_mode="MarkdownV2",
    )

    await ask_question(cb.message, state)
    await cb.answer()


async def ask_question(msg: Message, state: FSMContext) -> None:
    """Send the current question to the user."""
    data = await state.get_data()
    topic = data["topic"]
    level = data["level"]
    idx = data["idx"]

    question = QuizService.get_question(topic, level, idx)
    if not question:
        await msg.answer("❗ Ошибка: вопрос не найден. Нажми /start")
        await state.clear()
        return

    total = QuizService.get_question_count(topic, level)
    keyboard, _ = build_answers_keyboard(question["options"], idx)

    # Format question text
    question_text = question["question"]
    lines = question_text.splitlines()
    caption = f"❓ _Вопрос {idx + 1} из {total}_\n\n" f"*{escape_md(lines[0])}*"
    if len(lines) > 1:
        caption += "\n" + "\n".join(escape_md(line) for line in lines[1:])

    try:
        # Check if question has an image
        file_id = question.get("file_id")
        if file_id:
            await msg.answer_photo(
                file_id, caption=caption, reply_markup=keyboard, parse_mode="MarkdownV2"
            )
        else:
            await msg.answer(caption, reply_markup=keyboard, parse_mode="MarkdownV2")
    except TelegramBadRequest as e:
        logging.warning(f"Error sending question: {e}")
        # Fallback to text only
        await msg.answer(caption[:4000], reply_markup=keyboard, parse_mode="MarkdownV2")

    await state.set_state(QuizState.answering)


@router.callback_query(QuizState.answering, F.data.startswith("ans:"))
async def handle_answer(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Handle user's answer."""
    # Parse callback data
    try:
        _, qidx_str, opt_str = cb.data.split(":")
        qidx = int(qidx_str)
        opt = int(opt_str)
    except (ValueError, IndexError) as e:
        logging.error(f"Invalid callback format: {cb.data} - {e}")
        await cb.answer("❌ Ошибка обработки ответа")
        return

    lock = _get_answer_lock(cb.message.chat.id, cb.from_user.id)
    async with lock:
        # Re-read state after acquiring the lock. Another callback may have
        # already processed this question while this callback was waiting.
        data = await state.get_data()
        if qidx != data.get("idx"):
            await cb.answer("⚠️ Этот вопрос уже пройден", show_alert=True)
            return

        topic = data["topic"]
        level = data["level"]
        is_correct = QuizService.check_answer(topic, level, qidx, opt)

        results = [*data.get("results", [])]
        results.append({"idx": qidx, "correct": is_correct})
        next_idx = qidx + 1
        score = data.get("score", 0) + int(is_correct)
        await state.update_data(idx=next_idx, score=score, results=results)

        try:
            answered_keyboard = _build_answered_keyboard(
                cb.message.reply_markup, cb.data, is_correct
            )
            await cb.message.edit_reply_markup(reply_markup=answered_keyboard)
        except TelegramBadRequest:
            # The state lock still prevents duplicate processing if the
            # original message can no longer be edited.
            pass

    # Notify user
    await cb.answer("✅ Верно!" if is_correct else "❌ Неверно")

    # Check if quiz is complete
    total = QuizService.get_question_count(topic, level)
    if next_idx >= total:
        await show_results(cb.message, state, bot, cb.from_user.id)
    else:
        await ask_question(cb.message, state)


async def show_results(msg: Message, state: FSMContext, bot: Bot, user_id: int) -> None:
    """Show quiz results."""
    data = await state.get_data()
    topic = data["topic"]
    level = data["level"]
    score = data["score"]
    results = data["results"]

    # Update user's total scores
    UserService.add_quiz_result(user_id, level, score, len(results))

    # Update pinned score message
    await UserService.update_pinned_score(bot, user_id, msg.chat.id)

    # Build detailed results
    lines = []
    for i, item in enumerate(results):
        question = QuizService.get_question(topic, level, item["idx"])
        if question:
            mark = "✅" if item["correct"] else "❌"
            correct_answer = QuizService.get_correct_answer(topic, level, item["idx"])
            q_text = question["question"].splitlines()[0][:50]
            lines.append(
                f"{mark} *Вопрос {i + 1}:* {escape_md(q_text)}\n"
                f"   _Ответ: {escape_md(correct_answer or 'N/A')}_"
            )

    result_text = (
        f"🏁 *Тест завершён\\!*\n\n"
        f"📚 Тема: *{escape_md(get_topic_name(topic))}*\n"
        f"📊 Уровень: *{get_level_name(level)}*\n"
        f"✨ Результат: *{score}* из *{len(results)}*\n\n"
    )

    # Add detailed results if not too long
    if len(results) <= 20:
        result_text += "\n\n".join(lines)

    await msg.answer(
        result_text, reply_markup=build_restart_keyboard(), parse_mode="MarkdownV2"
    )

    # Clear quiz-specific state but keep level
    await state.update_data(topic=None, idx=0, score=0, results=[])
    await state.set_state(QuizState.selecting_topic)


@router.callback_query(F.data.startswith("topic:"))
async def handle_topic_without_state(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle topic selection when not in selecting_topic state."""
    data = await state.get_data()
    level = data.get("level")

    if not level:
        await cb.answer("Сначала выбери уровень", show_alert=True)
        from bot.keyboards import build_level_keyboard

        await cb.message.edit_text(
            "Выбери уровень сложности:", reply_markup=build_level_keyboard()
        )
        await state.set_state(QuizState.selecting_level)
        return

    # Set state and process
    await state.set_state(QuizState.selecting_topic)
    await choose_topic(cb, state)
