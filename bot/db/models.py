import json
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, BigInteger
from sqlalchemy.orm import declarative_base, sessionmaker, Session

Base = declarative_base()

DB_PATH = Path(__file__).parent.parent / "data" / "quiz_bot.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)


class User(Base):
    """User model for storing quiz progress."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    level = Column(String(20), nullable=True)  # junior, middle, senior

    # Scores stored as JSON: {"correct": X, "total": Y}
    scores_junior = Column(String(100), default='{"correct": 0, "total": 0}')
    scores_middle = Column(String(100), default='{"correct": 0, "total": 0}')
    scores_senior = Column(String(100), default='{"correct": 0, "total": 0}')

    # Pinned message ID for score display
    pinned_message_id = Column(BigInteger, nullable=True)

    def get_scores(self, level: str) -> dict:
        """Get scores for a specific level."""
        scores_field = getattr(self, f"scores_{level}", None)
        if scores_field:
            return json.loads(scores_field)
        return {"correct": 0, "total": 0}

    def set_scores(self, level: str, correct: int, total: int) -> None:
        """Set scores for a specific level."""
        setattr(
            self, f"scores_{level}", json.dumps({"correct": correct, "total": total})
        )

    def get_all_scores(self) -> dict:
        """Get scores for all levels."""
        return {
            "junior": self.get_scores("junior"),
            "middle": self.get_scores("middle"),
            "senior": self.get_scores("senior"),
        }


def init_db() -> None:
    """Initialize the database and create tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


def get_session() -> Session:
    """Get a database session."""
    return SessionLocal()
