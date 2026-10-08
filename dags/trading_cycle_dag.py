"""Apache Airflow DAG scheduling daily autonomous trading analysis cycles."""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from airflow.sdk import DAG, task

logger = logging.getLogger(__name__)

DAG_ID = "trading_cycle_dag"
DEFAULT_SCHEDULE = "0 21 * * 1-5"  # Weekdays at 21:00 UTC (after US market close)
DEFAULT_API_URL = "http://api:8080"
DEFAULT_RETRIES = 2
DEFAULT_RETRY_DELAY = timedelta(minutes=1)
DAG_TAGS = ["trading", "autonomous-analyst", "m5"]


def get_api_base_url() -> str:
    """Retrieve API base URL from environment or configuration default."""
    return os.getenv("AGENT_API_URL", DEFAULT_API_URL).rstrip("/")


def check_api_health_callable(
    api_url: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Verify API liveness and database connectivity."""
    base_url = api_url or get_api_base_url()
    url = f"{base_url}/health"

    logger.info("Checking API health at %s", url)
    response = httpx.get(url, timeout=timeout)
    response.raise_for_status()

    data: dict[str, Any] = response.json()
    status = data.get("status")
    if status != "ok":
        msg = f"API health reported status '{status}', expected 'ok'"
        logger.error(msg)
        raise RuntimeError(msg)

    logger.info("API is healthy: %s", data)
    return data


def trigger_cycle_callable(
    api_url: str | None = None,
    watchlist: list[str] | None = None,
    timeout: float = 300.0,
) -> dict[str, Any]:
    """Dispatch HTTP request to execute the autonomous analysis cycle."""
    base_url = api_url or get_api_base_url()
    url = f"{base_url}/cycles"
    payload: dict[str, Any] = {}
    if watchlist is not None:
        payload["watchlist"] = watchlist

    logger.info("Triggering trading analysis cycle at %s with payload %s", url, payload)
    response = httpx.post(url, json=payload, timeout=timeout)
    response.raise_for_status()

    data: dict[str, Any] = response.json()
    cycle_id = data.get("cycle_id", "unknown")
    decisions_count = len(data.get("decisions", []))
    orders_count = len(data.get("orders", []))
    fills_count = len(data.get("fills", []))
    equity = data.get("portfolio_state", {}).get("total_equity", 0.0)

    logger.info(
        "Trading cycle %s completed: %d decisions, %d orders, %d fills. Total equity: $%.2f",
        cycle_id,
        decisions_count,
        orders_count,
        fills_count,
        equity,
    )
    return data


@task(task_id="check_api_health")
def check_api_health() -> dict[str, Any]:
    """Evaluate API and database readiness before starting trading cycle."""
    return check_api_health_callable()


@task(task_id="trigger_trading_cycle")
def trigger_trading_cycle() -> dict[str, Any]:
    """Dispatch HTTP request to execute the daily trading analysis cycle."""
    return trigger_cycle_callable()


with DAG(
    dag_id=DAG_ID,
    description="Scheduled daily trading cycle orchestrator executing analysis via FastAPI.",
    schedule=DEFAULT_SCHEDULE,
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    catchup=False,
    tags=DAG_TAGS,
    default_args={
        "retries": DEFAULT_RETRIES,
        "retry_delay": DEFAULT_RETRY_DELAY,
    },
) as dag:
    health_check = check_api_health()
    cycle_trigger = trigger_trading_cycle()

    health_check >> cycle_trigger
