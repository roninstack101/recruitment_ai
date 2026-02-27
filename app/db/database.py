# app/db/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:wogom@localhost:5432/recruitment_ai",
)

# Render / Neon may provide postgres:// — SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Build connect args
connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args["check_same_thread"] = False
elif "localhost" not in DATABASE_URL and "127.0.0.1" not in DATABASE_URL:
    # Production DB — require SSL
    connect_args["sslmode"] = "require"

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # auto-reconnect on stale connections
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency – yields a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
