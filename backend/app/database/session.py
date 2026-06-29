from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.settings import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_NEW_COLUMNS: dict[str, dict[str, str]] = {
    "frames": {
        "question_score": "FLOAT DEFAULT 0",
        "is_question": "BOOLEAN DEFAULT 0",
        "is_duplicate": "BOOLEAN DEFAULT 0",
        "phash": "VARCHAR(64) DEFAULT ''",
        "ocr_text": "TEXT DEFAULT ''",
        "ocr_confidence": "FLOAT DEFAULT 0",
        "ocr_done": "BOOLEAN DEFAULT 0",
    },
    "questions": {
        "options": "TEXT DEFAULT ''",
        "source": "VARCHAR(20) DEFAULT 'manual'",
        "status": "VARCHAR(20) DEFAULT 'pending'",
        "ocr_confidence": "FLOAT DEFAULT 0",
        "frame_confidence": "FLOAT DEFAULT 0",
        "merge_confidence": "FLOAT DEFAULT 0",
        "overall_confidence": "FLOAT DEFAULT 0",
        "frame_start": "INTEGER",
        "frame_end": "INTEGER",
    },
}


def init_db() -> None:
    from app import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        for table, columns in _NEW_COLUMNS.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
