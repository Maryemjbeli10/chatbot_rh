"""
Base de données robuste : SQLite par défaut, PostgreSQL en production via DATABASE_URL.
"""

import os
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, text, Column, Integer, String, Text, DateTime, ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{SQLITE_PATH}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = Column(String(100))
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    sources = Column(Text)
    confidence = Column(String(20))
    language = Column(String(10))


class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    rating = Column(String(20), nullable=False)
    comment = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    Base.metadata.create_all(engine)


def log_conversation(user_id, question, answer, sources, confidence, language) -> int:
    with SessionLocal() as session:
        conv = Conversation(
            user_id=user_id, question=question, answer=answer,
            sources=", ".join(sources) if sources else "",
            confidence=confidence, language=language,
        )
        session.add(conv)
        session.commit()
        session.refresh(conv)
        return conv.id


def log_feedback(conversation_id: int, rating: str, comment: str = ""):
    with SessionLocal() as session:
        session.add(Feedback(conversation_id=conversation_id, rating=rating, comment=comment))
        session.commit()


def get_feedback_stats():
    with SessionLocal() as session:
        rows = session.execute(text("SELECT rating, COUNT(*) FROM feedback GROUP BY rating")).all()
        return dict(rows)


def get_history(user_id: str, limit: int = 50):
    with SessionLocal() as session:
        convs = (
            session.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.id.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": c.id,
                "timestamp": c.timestamp.isoformat() if c.timestamp else "",
                "question": c.question, "answer": c.answer, "sources": c.sources,
                "confidence": c.confidence, "language": c.language,
            }
            for c in convs
        ]


def get_usage_stats():
    with SessionLocal() as session:
        total_questions = session.query(Conversation).count()

        fb_rows = session.execute(text("SELECT rating, COUNT(*) FROM feedback GROUP BY rating")).all()
        fb = dict(fb_rows)
        total_fb = sum(fb.values())
        satisfaction = round(100 * fb.get("positive", 0) / total_fb) if total_fb else None

        source_counter = {}
        for (sources,) in session.query(Conversation.sources).filter(Conversation.sources != "").all():
            for s in sources.split(", "):
                if s:
                    source_counter[s] = source_counter.get(s, 0) + 1

        conf_rows = session.execute(text("SELECT confidence, COUNT(*) FROM conversations GROUP BY confidence")).all()
        confidence_counter = dict(conf_rows)

        return {
            "total_questions": total_questions,
            "satisfaction": satisfaction,
            "by_source": source_counter,
            "by_confidence": confidence_counter,
        }
