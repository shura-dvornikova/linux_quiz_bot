import logging
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.states import QuizState
from bot.keyboards import build_answers_keyboard, build_restart_keyboard
from bot.keyboards.builders import get_topic_name, get_level_name
from bot.services.quiz_service import QuizService
from bot.services.user_service import UserService, escape_md

router = Router()


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
    data = await state.get_data()
    topic = data["topic"]
    level = data["level"]

    # Parse callback data
    try:
        _, qidx_str, opt_str = cb.data.split(":")
        qidx = int(qidx_str)
        opt = int(opt_str)
    except (ValueError, IndexError) as e:
        logging.error(f"Invalid callback format: {cb.data} - {e}")
        await cb.answer("❌ Ошибка обработки ответа")
        return

    # Check if this is the current question
    if qidx != data["idx"]:
        await cb.answer("⚠️ Этот вопрос уже пройден", show_alert=True)
        return

    # Check answer
    is_correct = QuizService.check_answer(topic, level, qidx, opt)

    # Update state
    data["results"].append({"idx": qidx, "correct": is_correct})
    data["score"] += int(is_correct)
    data["idx"] += 1
    await state.update_data(**data)

    # Notify user
    await cb.answer("✅ Верно!" if is_correct else "❌ Неверно")

    # Check if quiz is complete
    total = QuizService.get_question_count(topic, level)
    if data["idx"] >= total:
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


@router.callback_query()
async def unknown_callback(cb: CallbackQuery) -> None:
    """Handle unknown callbacks."""
    await cb.answer(
        "⚠️ Действие устарело или сессия завершена. Нажми /start", show_alert=True
    )
