"""Databázové připojení a session."""
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import DATABASE_URL


def utc_now():
    """Aktuální čas v UTC (timezone-aware). Náhrada za deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Generator DB session. Flask používá g.db z before_request; get_db pro skripty/testy."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
