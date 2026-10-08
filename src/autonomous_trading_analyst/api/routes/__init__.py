"""API route modules exporting individual subrouters."""

from autonomous_trading_analyst.api.routes.cycles import router as cycles_router
from autonomous_trading_analyst.api.routes.decisions import router as decisions_router
from autonomous_trading_analyst.api.routes.health import router as health_router
from autonomous_trading_analyst.api.routes.portfolio import router as portfolio_router

__all__ = [
    "cycles_router",
    "decisions_router",
    "health_router",
    "portfolio_router",
]
