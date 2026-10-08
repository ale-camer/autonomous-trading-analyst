"""Health check endpoint evaluating service status and database connectivity."""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from autonomous_trading_analyst.api.dependencies import (
    get_session_factory_dep,
    get_settings_dep,
)
from autonomous_trading_analyst.api.schemas import HealthResponse
from autonomous_trading_analyst.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health(
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory_dep)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> HealthResponse:
    """Evaluate service health and execute an active database connectivity check."""
    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Database health check probe failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unreachable: {exc}",
        ) from exc

    return HealthResponse(
        status="ok",
        database="connected",
        app_env=settings.app_env,
        timestamp=datetime.now(UTC),
    )
