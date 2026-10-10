"""Database engine, session factory, declarative base and FastAPI dependency."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session for the duration of a request.

    Yields:
        An open SQLAlchemy Session that is closed afterwards.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
