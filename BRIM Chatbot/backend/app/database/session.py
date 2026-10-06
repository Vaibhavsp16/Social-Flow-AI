import logging
import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

logger = logging.getLogger("uvicorn")


def _allow_sqlite_fallback() -> bool:
    """Development convenience: allow degrading to SQLite when PostgreSQL is unreachable."""
    return os.getenv("ALLOW_SQLITE_FALLBACK", "true").lower() in ("1", "true", "yes")


def create_db_engine():
    db_url = settings.get_database_url()
    try:
        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        eng = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
        # Test connection
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"Database connected: {eng.dialect.name} ({_safe_url(db_url)})")
        return eng
    except Exception as e:
        if not _allow_sqlite_fallback():
            raise RuntimeError(
                f"Could not connect to the configured database ({_safe_url(db_url)}): {e}"
            ) from e

        logger.error(
            "Could not connect to the configured PostgreSQL database "
            f"({_safe_url(db_url)}): {e}\n"
            "  -> Falling back to local SQLite (brim_ai.db). Data written now will NOT be "
            "visible in PostgreSQL. Start PostgreSQL with `docker compose up -d` and make sure "
            "the configured driver is installed to use the real database."
        )
        fallback_url = "sqlite:///./brim_ai.db"
        return create_engine(fallback_url, connect_args={"check_same_thread": False})


def _safe_url(url: str) -> str:
    """Strip credentials before logging a database URL."""
    if "@" not in url:
        return url
    scheme, _, rest = url.partition("://")
    return f"{scheme}://***@{rest.split('@', 1)[1]}"


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_pgvector_extension():
    """Enable the pgvector extension so Vector columns can be created and queried."""
    if engine.dialect.name != "postgresql":
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception as e:
        logger.error(
            f"Could not enable the pgvector extension: {e}. "
            "Semantic search will fall back to in-memory cosine scoring."
        )


def _sync_schema():
    """
    Add columns that exist on the models but are missing from pre-existing tables.

    ``Base.metadata.create_all()`` only creates *new* tables, so a database created by an
    older revision of the models keeps its old columns. Without this, every query touching
    the new column fails (e.g. "no such column: knowledge_chunks.embedding_vector") and the
    knowledge pipeline silently produces no chunks.
    """
    from app.models import Base as ModelsBase

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table in ModelsBase.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_columns = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_columns:
                continue
            col_type = column.type.compile(dialect=engine.dialect)
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'
            try:
                with engine.begin() as conn:
                    conn.execute(text(ddl))
                logger.warning(
                    f"Schema drift repaired: added missing column {table.name}.{column.name} ({col_type})"
                )
            except Exception as e:
                logger.error(f"Could not add missing column {table.name}.{column.name}: {e}")


def init_db():
    from app.models import Base as ModelsBase

    _ensure_pgvector_extension()
    ModelsBase.metadata.create_all(bind=engine)
    _sync_schema()
