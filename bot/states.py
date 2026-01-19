from aiogram.fsm.state import State, StatesGroup


class QuizState(StatesGroup):
    """FSM states for the quiz bot user flow."""

    entering_name = State()  # User is entering their name
    selecting_level = State()  # User is selecting difficulty level
    selecting_topic = State()  # User is selecting a topic
    answering = State()  # User is answering quiz questions
    waiting_for_feedback = State()  # User is writing feedback
