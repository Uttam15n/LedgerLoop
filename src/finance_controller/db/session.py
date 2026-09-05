"""
Database engine + session factory.

This is the ONLY file in the project that knows the actual database
connection string. Everything else (repository.py, matcher, agents) asks
this file for a session instead of importing sqlite3 or a connection
string directly.

Why this matters in practice: if you ever move from SQLite to Postgres
(e.g. for a real production deployment), this is the only file that changes.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from finance_controller.config.settings import DATABASE_URL
from finance_controller.db.models import Base


engine = create_engine(DATABASE_URL, echo=False)


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """
    Create all tables defined in db/models.py, if they don't already exist.

    Safe to call every time the app starts — it will NOT drop or overwrite
    existing data, it only creates tables that are missing.
    """
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """
    Return a new database session.

    Usage:
        session = get_session()
        try:
            ...
            session.commit()
        finally:
            session.close()

    Later files (repository.py) wrap this in a cleaner context-manager
    pattern — this function is the low-level building block.
    """
    return SessionLocal()