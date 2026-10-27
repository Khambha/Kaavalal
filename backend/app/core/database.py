
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import BASE_DIR, settings


# Read the database URL from backend/.env
DATABASE_URL = settings.DATABASE_URL

# Configure SSL when a CA certificate is supplied.
connect_args = {}

if settings.MYSQL_SSL_CA:
    ca_path = Path(settings.MYSQL_SSL_CA)

    # Relative certificate paths are resolved from the backend directory.
    if not ca_path.is_absolute():
        ca_path = BASE_DIR / ca_path

    if not ca_path.is_file():
        raise RuntimeError(
            f"MySQL CA certificate not found: {ca_path}. "
            "Check MYSQL_SSL_CA in your backend .env file."
        )

    connect_args["ssl"] = {
        "ca": str(ca_path),
    }


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
