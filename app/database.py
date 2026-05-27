"""
database.py
-----------
SQLAlchemy engine, session factory, and FastAPI dependency for Buea Market Watch.

Dev target  : SQLite  (sqlite:///./market_watch.db)
Prod target : PostgreSQL (injected via DATABASE_URL environment variable)
"""

import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# ---------------------------------------------------------------------------
# Engine configuration
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./market_watch.db")

# Railway (and older Heroku) emit "postgres://" — SQLAlchemy 1.4+ requires
# the "postgresql://" scheme.  Normalise here so both work transparently.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs check_same_thread=False for use inside FastAPI worker threads.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,          # Set True to log all SQL statements during debugging
)

# ---------------------------------------------------------------------------
# Enforce SQLite foreign-key constraints at the connection level
# ---------------------------------------------------------------------------

@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Activate PRAGMA foreign_keys = ON for every new SQLite connection."""
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Declarative base (shared by all ORM models)
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Project-wide declarative base for all SQLAlchemy ORM models."""
    pass


# ---------------------------------------------------------------------------
# FastAPI dependency — yields a DB session and guarantees cleanup
# ---------------------------------------------------------------------------

def get_db():
    """
    FastAPI dependency that provides a transactional database session.

    Usage in route handlers::

        @app.post("/...")
        def my_route(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
