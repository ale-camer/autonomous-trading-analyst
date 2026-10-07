"""Database engine configuration, session management, and schema initialization."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from autonomous_trading_analyst.persistence.models import Base


def create_db_engine(url: str, echo: bool = False) -> Engine:
    """Create a SQLAlchemy Engine configured for application or testing workloads."""
    return create_engine(url, echo=echo, future=True)


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
