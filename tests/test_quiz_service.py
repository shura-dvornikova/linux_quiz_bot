import json

from bot.services.quiz_service import QuizService


def test_reference_is_loaded_from_references_file(tmp_path, monkeypatch):
    quizzes_path = tmp_path / "quizzes.json"
    references_path = tmp_path / "references.json"
    quizzes_path.write_text(
        json.dumps(
            {
                "bash": {
                    "title": "Bash",
                    "junior": [
                        {
                            "question": "Что делает pwd?",
                            "options": ["Путь", "Файл"],
                            "correct": 0,
                            "reference": "This embedded value must be ignored.",
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    references_path.write_text(
        json.dumps({"bash": {"junior": {"0": "pwd показывает текущий каталог."}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr("bot.services.quiz_service.QUIZ_PATH", quizzes_path)
    monkeypatch.setattr("bot.services.quiz_service.REFERENCES_PATH", references_path)
    monkeypatch.setattr(QuizService, "_quizzes", None)
    monkeypatch.setattr(QuizService, "_references", None)

    assert QuizService.get_reference("bash", "junior", 0) == (
        "pwd показывает текущий каталог."
    )


def test_missing_reference_returns_empty_string(tmp_path, monkeypatch):
    quizzes_path = tmp_path / "quizzes.json"
    references_path = tmp_path / "references.json"
    quizzes_path.write_text(
        json.dumps(
            {
                "bash": {
                    "title": "Bash",
                    "junior": [
                        {
                            "question": "Что делает pwd?",
                            "options": ["Путь", "Файл"],
                            "correct": 0,
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    references_path.write_text(json.dumps({"bash": {"junior": {}}}), encoding="utf-8")

    monkeypatch.setattr("bot.services.quiz_service.QUIZ_PATH", quizzes_path)
    monkeypatch.setattr("bot.services.quiz_service.REFERENCES_PATH", references_path)
    monkeypatch.setattr(QuizService, "_quizzes", None)
    monkeypatch.setattr(QuizService, "_references", None)

    assert QuizService.get_reference("bash", "junior", 0) == ""
