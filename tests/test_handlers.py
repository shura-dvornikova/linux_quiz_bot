import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.handlers import setup_routers
from bot.handlers.feedback import handle_feedback, router as feedback_router
from bot.handlers.fallback import router as fallback_router
from bot.handlers.quiz import (
    _build_answer_feedback,
    _build_answered_reference_keyboard,
    _build_answered_keyboard,
    handle_answer,
    show_reference,
)
from bot.handlers.start import process_level, process_name
from bot.db.models import User
from bot.config import get_feedback_chat_id


class FakeState:
    def __init__(self, data):
        self.data = data

    async def get_data(self):
        await asyncio.sleep(0)
        return dict(self.data)

    async def update_data(self, **kwargs):
        await asyncio.sleep(0)
        self.data.update(kwargs)

    async def clear(self):
        await asyncio.sleep(0)
        self.data.clear()


def test_feedback_router_is_registered_before_callback_fallback():
    routers = setup_routers().sub_routers

    assert routers.index(feedback_router) < routers.index(fallback_router)


def test_feedback_destination_accepts_id_and_channel_username():
    assert get_feedback_chat_id(" -10012345 ") == -10012345
    assert get_feedback_chat_id("@linux_quiz_feedback") == "@linux_quiz_feedback"


def test_feedback_is_delivered_to_configured_receiver():
    async def run_test():
        state = FakeState({"pending": True})
        message = SimpleNamespace(
            text="Great quiz!",
            from_user=SimpleNamespace(
                id=20, username="student", full_name="Test Student"
            ),
            answer=AsyncMock(),
        )
        bot = AsyncMock()

        with patch("bot.handlers.feedback.feedback_channel_id", "-10012345"):
            await handle_feedback(message, state, bot)

        bot.send_message.assert_awaited_once()
        assert bot.send_message.await_args.kwargs["chat_id"] == -10012345
        assert "Great quiz!" in bot.send_message.await_args.kwargs["text"]
        assert bot.send_message.await_args.kwargs["parse_mode"] is None
        message.answer.assert_awaited_once_with("Спасибо за отзыв! 💌")
        assert state.data == {}

    asyncio.run(run_test())


def test_feedback_failure_is_reported_and_state_is_kept():
    async def run_test():
        state = FakeState({"pending": True})
        message = SimpleNamespace(
            text="Feedback",
            from_user=SimpleNamespace(id=20, username=None, full_name="Student"),
            answer=AsyncMock(),
        )
        bot = AsyncMock()
        bot.send_message.side_effect = ValueError("invalid chat id")

        with patch("bot.handlers.feedback.feedback_channel_id", "invalid"):
            await handle_feedback(message, state, bot)

        message.answer.assert_awaited_once_with(
            "Не удалось отправить отзыв. Попробуй позже."
        )
        assert state.data == {"pending": True}

    asyncio.run(run_test())


def test_duplicate_answers_are_processed_once():
    async def run_test():
        state = FakeState(
            {
                "topic": "bash",
                "level": "junior",
                "idx": 0,
                "score": 0,
                "results": [],
            }
        )
        message = SimpleNamespace(
            chat=SimpleNamespace(id=10),
            answer=AsyncMock(),
            edit_caption=AsyncMock(),
            edit_text=AsyncMock(),
            edit_reply_markup=AsyncMock(),
            photo=None,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="First", callback_data="ans:0:0")],
                    [InlineKeyboardButton(text="Second", callback_data="ans:0:1")],
                ]
            ),
        )

        def callback():
            return SimpleNamespace(
                data="ans:0:1",
                message=message,
                from_user=SimpleNamespace(id=20),
                answer=AsyncMock(),
            )

        first = callback()
        duplicate = callback()

        with (
            patch(
                "bot.handlers.quiz.QuizService.check_answer",
                return_value=True,
            ) as check_answer,
            patch("bot.handlers.quiz.QuizService.get_question_count", return_value=2),
            patch(
                "bot.handlers.quiz.QuizService.get_correct_answer",
                return_value="Second",
            ),
            patch(
                "bot.handlers.quiz.QuizService.get_reference",
                return_value="Short reference",
            ),
            patch(
                "bot.handlers.quiz.QuizService.get_question",
                return_value={"question": "Test question"},
            ),
            patch(
                "bot.handlers.quiz.ask_question", new_callable=AsyncMock
            ) as ask_question,
        ):
            await asyncio.gather(
                handle_answer(first, state, AsyncMock()),
                handle_answer(duplicate, state, AsyncMock()),
            )

        assert state.data["idx"] == 1
        assert state.data["score"] == 1
        assert state.data["results"] == [{"idx": 0, "correct": True}]
        check_answer.assert_called_once()
        ask_question.assert_awaited_once()
        message.edit_text.assert_awaited_once_with(
            "❓ _Вопрос 1 из 2_\n\n*Test question*\n\n" "✅ Верно\\!\n*Ответ:* Second",
            reply_markup=_build_answered_reference_keyboard(
                message.reply_markup,
                "ans:0:1",
                "bash",
                "junior",
                0,
                True,
            ),
            parse_mode="MarkdownV2",
        )
        message.answer.assert_not_awaited()
        answered_keyboard = message.edit_text.await_args.kwargs["reply_markup"]
        assert answered_keyboard.inline_keyboard[0][0].text == "First"
        assert answered_keyboard.inline_keyboard[1][0].text == "✅ Second"
        assert answered_keyboard.inline_keyboard[2][0].text == "🔗 Краткая справка"
        answers = [first.answer.await_args.args, duplicate.answer.await_args.args]
        assert ("✅ Верно!",) in answers
        assert ("⚠️ Этот вопрос уже пройден",) in answers

    asyncio.run(run_test())


def test_answered_keyboard_marks_incorrect_selection():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="First", callback_data="ans:0:0")],
            [InlineKeyboardButton(text="Second", callback_data="ans:0:1")],
        ]
    )

    answered_keyboard = _build_answered_keyboard(keyboard, "ans:0:0", False)

    assert answered_keyboard.inline_keyboard[0][0].text == "❌ First"
    assert answered_keyboard.inline_keyboard[1][0].text == "Second"


def test_non_text_name_is_rejected():
    async def run_test():
        message = SimpleNamespace(text=None, answer=AsyncMock())
        state = FakeState({})

        await process_name(message, state)

        message.answer.assert_awaited_once_with(
            "Пожалуйста, введи корректное имя (до 100 символов):"
        )

    asyncio.run(run_test())


def test_unknown_level_callback_is_rejected():
    async def run_test():
        callback = SimpleNamespace(data="level:invalid", answer=AsyncMock())

        await process_level(callback, FakeState({}), AsyncMock())

        callback.answer.assert_awaited_once_with("Неизвестный уровень", show_alert=True)

    asyncio.run(run_test())


def test_user_scores_reject_unknown_level():
    user = User()

    try:
        user.set_scores("invalid", 1, 1)
    except ValueError as error:
        assert str(error) == "Unsupported quiz level: invalid"
    else:
        raise AssertionError("Unknown level must not create an arbitrary model field")


def test_answer_feedback_expands_and_escapes_reference():
    with (
        patch(
            "bot.handlers.quiz.QuizService.get_correct_answer",
            return_value="ls -la",
        ),
        patch(
            "bot.handlers.quiz.QuizService.get_reference",
            return_value="Показывает файлы, включая .скрытые",
        ),
    ):
        text = _build_answer_feedback(
            "bash", "junior", 0, False, include_reference=True
        )

    assert text == (
        "❌ Неверно\\!\n"
        "*Ответ:* ls \\-la\n\n"
        "*Краткая справка:*\nПоказывает файлы, включая \\.скрытые"
    )


def test_show_reference_expands_answer_message():
    async def run_test():
        message = SimpleNamespace(edit_text=AsyncMock(), photo=None)
        callback = SimpleNamespace(
            data="ref:bash:junior:0:1",
            message=message,
            answer=AsyncMock(),
        )

        with (
            patch(
                "bot.handlers.quiz.QuizService.get_question",
                return_value={"question": "What does echo do?"},
            ),
            patch("bot.handlers.quiz.QuizService.get_question_count", return_value=20),
            patch(
                "bot.handlers.quiz.QuizService.get_correct_answer",
                return_value="echo",
            ),
            patch(
                "bot.handlers.quiz.QuizService.get_reference",
                return_value="Выводит аргументы в стандартный поток вывода.",
            ),
        ):
            await show_reference(callback)

        message.edit_text.assert_awaited_once_with(
            "❓ _Вопрос 1 из 20_\n\n*What does echo do?*\n\n"
            "✅ Верно\\!\n*Ответ:* echo\n\n"
            "*Краткая справка:*\n"
            "Выводит аргументы в стандартный поток вывода\\.",
            reply_markup=None,
            parse_mode="MarkdownV2",
        )
        callback.answer.assert_awaited_once_with()

    asyncio.run(run_test())


def test_show_reference_edits_photo_caption():
    async def run_test():
        message = SimpleNamespace(edit_caption=AsyncMock(), photo=[object()])
        callback = SimpleNamespace(
            data="ref:bash:junior:0:0",
            message=message,
            answer=AsyncMock(),
        )

        with (
            patch(
                "bot.handlers.quiz.QuizService.get_question",
                return_value={"question": "Photo question"},
            ),
            patch("bot.handlers.quiz.QuizService.get_question_count", return_value=1),
            patch(
                "bot.handlers.quiz.QuizService.get_correct_answer",
                return_value="Answer",
            ),
            patch(
                "bot.handlers.quiz.QuizService.get_reference",
                return_value="Reference",
            ),
        ):
            await show_reference(callback)

        message.edit_caption.assert_awaited_once_with(
            caption=(
                "❓ _Вопрос 1 из 1_\n\n*Photo question*\n\n"
                "❌ Неверно\\!\n*Ответ:* Answer\n\n"
                "*Краткая справка:*\nReference"
            ),
            reply_markup=None,
            parse_mode="MarkdownV2",
        )

    asyncio.run(run_test())
