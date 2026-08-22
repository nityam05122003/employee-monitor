"""
SQLAlchemy engine/session setup. DATABASE_URL comes from config.py — swapping
to Postgres later is just changing that URL, since no SQLite-specific SQL is
used anywhere in the app.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# check_same_thread=False: SQLite connections are normally bound to the thread
# that created them, but our recognition loop runs in a background thread and
# needs to open its own short-lived sessions. Only needed for SQLite.
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables if they don't exist yet. Called on app startup."""
    import app.models  # noqa: F401 (ensure models are registered on Base before create_all)
    Base.metadata.create_all(bind=engine)
