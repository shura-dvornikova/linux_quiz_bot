import random
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Level display names
LEVELS = {
    "junior": "Junior",
    "middle": "Middle",
    "senior": "Senior",
}

# Topic display names (Russian)
TOPICS = {
    "file_systems": "Файловые системы",
    "permissions": "Права и пользователи",
    "processes": "Процессы",
    "resources": "Системные ресурсы",
    "systemd": "Сервисы (systemd)",
    "networking": "Сети",
    "boot": "Загрузка ОС",
    "bash": "Bash и автоматизация",
}


def build_level_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for level selection."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"level:{key}")]
            for key, name in LEVELS.items()
        ]
    )


def build_topics_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for topic selection."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"topic:{key}")]
            for key, name in TOPICS.items()
        ]
    )


def build_answers_keyboard(
    options: list[str], question_idx: int, shuffle: bool = True
) -> tuple[InlineKeyboardMarkup, list[int]]:
    """
    Build keyboard for answer options.

    Returns:
        tuple: (keyboard, order) where order maps display position to original index
    """
    indices = list(range(len(options)))
    if shuffle:
        random.shuffle(indices)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=options[i], callback_data=f"ans:{question_idx}:{i}"
                )
            ]
            for i in indices
        ]
    )
    return keyboard, indices


def build_restart_keyboard(include_feedback: bool = True) -> InlineKeyboardMarkup:
    """Build keyboard for restart/continue options."""
    buttons = [
        [InlineKeyboardButton(text="Выбрать тему", callback_data="select_topic")],
        [InlineKeyboardButton(text="Сменить уровень", callback_data="select_level")],
    ]
    if include_feedback:
        buttons.append(
            [InlineKeyboardButton(text="Оставить отзыв", callback_data="feedback")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_feedback_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard with feedback button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оставить отзыв", callback_data="feedback")]
        ]
    )


def get_topic_name(topic_key: str) -> str:
    """Get display name for a topic."""
    return TOPICS.get(topic_key, topic_key)


def get_level_name(level_key: str) -> str:
    """Get display name for a level."""
    return LEVELS.get(level_key, level_key)
