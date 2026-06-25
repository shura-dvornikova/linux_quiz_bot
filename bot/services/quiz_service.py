import json
from pathlib import Path
from typing import Optional

QUIZ_PATH = Path(__file__).parent.parent / "data" / "quizzes.json"
REFERENCES_PATH = Path(__file__).parent.parent / "data" / "references.json"


class QuizService:
    """Service for quiz data operations."""

    _quizzes: Optional[dict] = None
    _references: Optional[dict] = None

    @classmethod
    def load_quizzes(cls) -> dict:
        """Load quizzes from JSON file."""
        if cls._quizzes is None:
            with QUIZ_PATH.open(encoding="utf-8") as f:
                cls._quizzes = json.load(f)
        return cls._quizzes

    @classmethod
    def load_references(cls) -> dict:
        """Load manually written short references from JSON file."""
        if cls._references is None:
            with REFERENCES_PATH.open(encoding="utf-8") as f:
                cls._references = json.load(f)
        return cls._references

    @classmethod
    def get_topics(cls) -> list[str]:
        """Get list of available topic keys."""
        quizzes = cls.load_quizzes()
        return list(quizzes.keys())

    @classmethod
    def get_topic_title(cls, topic: str) -> str:
        """Get display title for a topic."""
        quizzes = cls.load_quizzes()
        if topic in quizzes:
            return quizzes[topic].get("title", topic)
        return topic

    @classmethod
    def get_questions(cls, topic: str, level: str) -> list[dict]:
        """Get questions for a specific topic and level."""
        quizzes = cls.load_quizzes()
        if topic in quizzes and level in quizzes[topic]:
            return quizzes[topic][level]
        return []

    @classmethod
    def get_question(cls, topic: str, level: str, index: int) -> Optional[dict]:
        """Get a specific question."""
        questions = cls.get_questions(topic, level)
        if 0 <= index < len(questions):
            return questions[index]
        return None

    @classmethod
    def get_question_count(cls, topic: str, level: str) -> int:
        """Get number of questions for a topic and level."""
        return len(cls.get_questions(topic, level))

    @classmethod
    def check_answer(
        cls, topic: str, level: str, question_idx: int, answer_idx: int
    ) -> bool:
        """Check if the answer is correct."""
        question = cls.get_question(topic, level, question_idx)
        if question:
            correct = question.get("correct")
            # Handle both int and str types for backwards compatibility
            return answer_idx == int(correct)
        return False

    @classmethod
    def get_correct_answer(
        cls, topic: str, level: str, question_idx: int
    ) -> Optional[str]:
        """Get the correct answer text for a question."""
        question = cls.get_question(topic, level, question_idx)
        if question:
            correct_idx = int(question.get("correct", 0))
            options = question.get("options", [])
            if 0 <= correct_idx < len(options):
                return options[correct_idx]
        return None

    @classmethod
    def get_reference(cls, topic: str, level: str, question_idx: int) -> str:
        """Get a short reference shown after answering a question."""
        question = cls.get_question(topic, level, question_idx)
        if not question:
            return ""

        references = cls.load_references()
        reference = references.get(topic, {}).get(level, {}).get(str(question_idx), "")
        if not reference:
            return ""

        lines = str(reference).splitlines()[:3]
        return "\n".join(line.strip() for line in lines if line.strip())
