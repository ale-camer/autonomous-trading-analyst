"""FastAPI application factory and configuration for Autonomous Trading Analyst."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from autonomous_trading_analyst.api.dependencies import get_settings_dep
from autonomous_trading_analyst.api.routes import (
    cycles_router,
    decisions_router,
    health_router,
    portfolio_router,
)
from autonomous_trading_analyst.config import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan startup and teardown events."""
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a new FastAPI application instance."""
    app = FastAPI(
        title="Autonomous Trading Analyst API",
        description=(
            "RESTful API for autonomous trading analysis cycles, decisions, "
            "and portfolio management."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    if settings is not None:
        app.dependency_overrides[get_settings_dep] = lambda: settings

    app.include_router(health_router)
    app.include_router(cycles_router)
    app.include_router(portfolio_router)
    app.include_router(decisions_router)

    return app


app = create_app()
