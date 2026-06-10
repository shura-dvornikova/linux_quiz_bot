import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.handlers import setup_routers
from bot.handlers.feedback import router as feedback_router
from bot.handlers.fallback import router as fallback_router
from bot.handlers.quiz import (
    _build_answer_feedback,
    _build_answered_keyboard,
    _build_reference_keyboard,
    handle_answer,
    show_reference,
)


class FakeState:
    def __init__(self, data):
        self.data = data

    async def get_data(self):
        await asyncio.sleep(0)
        return dict(self.data)

    async def update_data(self, **kwargs):
        await asyncio.sleep(0)
        self.data.update(kwargs)


def test_feedback_router_is_registered_before_callback_fallback():
    routers = setup_routers().sub_routers

    assert routers.index(feedback_router) < routers.index(fallback_router)


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
            edit_reply_markup=AsyncMock(),
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
        message.answer.assert_awaited_once_with(
            "✅ Верно\\!\n*Ответ:* Second",
            reply_markup=_build_reference_keyboard("bash", "junior", 0, True),
            parse_mode="MarkdownV2",
        )
        answered_keyboard = message.edit_reply_markup.await_args.kwargs["reply_markup"]
        assert answered_keyboard.inline_keyboard[0][0].text == "First"
        assert answered_keyboard.inline_keyboard[1][0].text == "✅ Second"
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
        message = SimpleNamespace(edit_text=AsyncMock())
        callback = SimpleNamespace(
            data="ref:bash:junior:0:1",
            message=message,
            answer=AsyncMock(),
        )

        with (
            patch(
                "bot.handlers.quiz.QuizService.get_question",
                return_value={"question": "Test"},
            ),
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
            "✅ Верно\\!\n*Ответ:* echo\n\n"
            "*Краткая справка:*\n"
            "Выводит аргументы в стандартный поток вывода\\.",
            reply_markup=None,
            parse_mode="MarkdownV2",
        )
        callback.answer.assert_awaited_once_with()

    asyncio.run(run_test())
