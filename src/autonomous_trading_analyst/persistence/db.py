"""Database engine configuration, session management, and schema initialization."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from autonomous_trading_analyst.persistence.models import Base


def create_db_engine(url: str, echo: bool = False) -> Engine:
    """Create a SQLAlchemy Engine configured for application or testing workloads."""
    import re
    clean_url = re.sub(r"^postgres(ql)?(\+[a-zA-Z0-9_]+)?://", "postgresql+psycopg://", url) if not url.startswith("sqlite") else url
    engine = create_engine(clean_url, echo=echo, future=True)

    if not clean_url.startswith("sqlite"):
        from sqlalchemy import event
        @event.listens_for(engine, "connect")
        def set_search_path(dbapi_connection, connection_record):
            with dbapi_connection.cursor() as cur:
                cur.execute("SET search_path TO p10_trading, public;")

    return engine


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a thread-safe sessionmaker factory bound to the provided engine."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Idempotently create all tables defined in the declarative Base schema."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db_session(
    session_factory: sessionmaker[Session],
) -> Generator[Session, None, None]:
    """Provide a transactional database session scope with automatic commit/rollback."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
