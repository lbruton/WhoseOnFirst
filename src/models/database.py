"""
Database configuration and session management for WhoseOnFirst.

This module sets up SQLAlchemy engine, session factory, and base model.
Uses environment variables for configuration.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/whoseonfirst.db")

# Create engine with appropriate settings
if DATABASE_URL.startswith("sqlite"):
    # SQLite-specific configuration
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Allow SQLite to work with FastAPI
        poolclass=NullPool,  # Fresh connection per request — avoids thread contention
        echo=os.getenv("DEBUG", "False").lower() == "true",  # Log SQL if DEBUG=True
    )
else:
    # PostgreSQL or other database configuration
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=int(os.getenv("DATABASE_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", "10")),
        echo=os.getenv("DEBUG", "False").lower() == "true",
    )

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create declarative base for models
Base = declarative_base()


def get_db():
    """
    Dependency function for FastAPI to get database session.

    Yields a database session and ensures it's closed after use.
    Use with FastAPI's Depends() for automatic session management.

    Example:
        @app.get("/items/")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database by creating all tables.

    Should be called on application startup.
    For production, use Alembic migrations instead.
    """
    Base.metadata.create_all(bind=engine)


def drop_db():
    """
    Drop all database tables.

    WARNING: This will delete all data!
    Only use for testing or development.
    """
    Base.metadata.drop_all(bind=engine)
