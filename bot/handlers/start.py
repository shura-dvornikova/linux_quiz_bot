from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.states import QuizState
from bot.keyboards import build_level_keyboard, build_topics_keyboard
from bot.keyboards.builders import get_level_name
from bot.services.user_service import UserService, escape_md
from bot.db.repository import UserRepository

router = Router()


@router.message(Command("start"))
async def cmd_start(msg: Message, state: FSMContext) -> None:
    """Handle /start command - begin the onboarding flow."""
    await state.clear()

    # Check if user exists
    user = UserService.get_user(msg.from_user.id)

    if user:
        # Returning user - show welcome back and go to level selection
        await msg.answer(
            f"С возвращением, *{escape_md(user.name)}*\\! 🎉\n\n"
            "Выбери уровень сложности:",
            reply_markup=build_level_keyboard(),
            parse_mode="MarkdownV2",
        )
        await state.set_state(QuizState.selecting_level)
    else:
        # New user - ask for name
        await msg.answer(
            "🤓 *Что умеет этот бот?*\n\n"
            "Привет\\! Я бот для тестирования знаний Linux\\.\n"
            "Помогу тебе подготовиться к собеседованию на DevOps\\!\n\n"
            "Введи своё имя:",
            parse_mode="MarkdownV2",
        )
        await state.set_state(QuizState.entering_name)


@router.message(Command("level"))
async def cmd_level(msg: Message, state: FSMContext) -> None:
    """Open level selection from the bot commands menu."""
    user = UserService.get_user(msg.from_user.id)
    if not user:
        await msg.answer("Сначала запусти бота командой /start")
        return

    await state.clear()
    await msg.answer(
        "Выбери уровень сложности:", reply_markup=build_level_keyboard()
    )
    await state.set_state(QuizState.selecting_level)


@router.message(Command("theme"))
async def cmd_theme(msg: Message, state: FSMContext) -> None:
    """Open topic selection from the bot commands menu."""
    user = UserService.get_user(msg.from_user.id)
    if not user:
        await msg.answer("Сначала запусти бота командой /start")
        return

    data = await state.get_data()
    level = data.get("level") or user.level
    if not level:
        await msg.answer(
            "Сначала выбери уровень:", reply_markup=build_level_keyboard()
        )
        await state.set_state(QuizState.selecting_level)
        return

    await state.clear()
    await state.update_data(level=level)
    await msg.answer(
        f"Уровень: *{get_level_name(level)}*\n\nВыбери тему:",
        reply_markup=build_topics_keyboard(),
        parse_mode="MarkdownV2",
    )
    await state.set_state(QuizState.selecting_topic)


@router.message(QuizState.entering_name)
async def process_name(msg: Message, state: FSMContext) -> None:
    """Process user's name input."""
    name = msg.text.strip()

    if not name or len(name) > 100:
        await msg.answer("Пожалуйста, введи корректное имя (до 100 символов):")
        return

    # Create user in database
    UserRepository.create(msg.from_user.id, name)

    await msg.answer(
        f"Приятно познакомиться, *{escape_md(name)}*\\! 👋\n\n" "Выбери свой уровень:",
        reply_markup=build_level_keyboard(),
        parse_mode="MarkdownV2",
    )
    await state.set_state(QuizState.selecting_level)


@router.callback_query(QuizState.selecting_level, F.data.startswith("level:"))
async def process_level(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Process level selection."""
    level = cb.data.split(":", 1)[1]

    # Update user's level
    UserService.set_level(cb.from_user.id, level)

    # Update pinned score message
    await UserService.update_pinned_score(bot, cb.from_user.id, cb.message.chat.id)

    await cb.message.edit_text(
        f"Уровень: *{get_level_name(level)}* ✅\n\n" "Теперь выбери тему:",
        reply_markup=build_topics_keyboard(),
        parse_mode="MarkdownV2",
    )
    await state.update_data(level=level)
    await state.set_state(QuizState.selecting_topic)
    await cb.answer()


@router.callback_query(F.data == "select_level")
async def select_level_again(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle request to change level."""
    await cb.message.edit_text(
        "Выбери уровень сложности:", reply_markup=build_level_keyboard()
    )
    await state.set_state(QuizState.selecting_level)
    await cb.answer()


@router.callback_query(F.data == "select_topic")
async def select_topic_again(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle request to select another topic."""
    data = await state.get_data()
    level = data.get("level")

    if not level:
        # No level set, go back to level selection
        await cb.message.edit_text(
            "Сначала выбери уровень:", reply_markup=build_level_keyboard()
        )
        await state.set_state(QuizState.selecting_level)
    else:
        await cb.message.edit_text(
            f"Уровень: *{get_level_name(level)}*\n\n" "Выбери тему:",
            reply_markup=build_topics_keyboard(),
            parse_mode="MarkdownV2",
        )
        await state.set_state(QuizState.selecting_topic)
    await cb.answer()
