"""Unit and integrity tests for the Airflow trading-cycle DAG."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from airflow.dag_processing.dagbag import DagBag
from dags.trading_cycle_dag import (
    DAG_ID,
    DAG_TAGS,
    DEFAULT_RETRIES,
    DEFAULT_RETRY_DELAY,
    DEFAULT_SCHEDULE,
    check_api_health,
    check_api_health_callable,
    get_api_base_url,
    trigger_cycle_callable,
    trigger_trading_cycle,
)


@pytest.fixture(scope="module")
def dag_bag() -> DagBag:
    """Load the DagBag for all DAGs in the dags directory."""
    return DagBag(dag_folder="dags")


@pytest.mark.issue_23
def test_dag_bag_import_errors(dag_bag: DagBag) -> None:
    """DagBag parses all DAG files with zero import errors."""
    assert len(dag_bag.import_errors) == 0, (
        f"DagBag failed to import DAGs with errors: {dag_bag.import_errors}"
    )


@pytest.mark.issue_23
def test_dag_structure_and_metadata(dag_bag: DagBag) -> None:
    """trading_cycle_dag exists with intended schedule, tags, and retry parameters."""
    dag = dag_bag.get_dag(DAG_ID)
    assert dag is not None, f"DAG '{DAG_ID}' was not found in DagBag"
    assert dag.schedule == DEFAULT_SCHEDULE
    assert dag.catchup is False
    assert set(dag.tags) == set(DAG_TAGS)
    assert dag.default_args["retries"] == DEFAULT_RETRIES
    assert dag.default_args["retry_delay"] == DEFAULT_RETRY_DELAY


@pytest.mark.issue_23
def test_dag_task_topology(dag_bag: DagBag) -> None:
    """trading_cycle_dag contains check_api_health upstream of trigger_trading_cycle."""
    dag = dag_bag.get_dag(DAG_ID)
    assert dag is not None

    task_ids = [t.task_id for t in dag.tasks]
    assert "check_api_health" in task_ids
    assert "trigger_trading_cycle" in task_ids

    health_task = dag.get_task("check_api_health")
    cycle_task = dag.get_task("trigger_trading_cycle")
    assert cycle_task in health_task.downstream_list


@pytest.mark.issue_23
def test_get_api_base_url_default_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_api_base_url respects AGENT_API_URL and trims trailing slashes."""
    monkeypatch.delenv("AGENT_API_URL", raising=False)
    assert get_api_base_url() == "http://api:8080"

    monkeypatch.setenv("AGENT_API_URL", "http://custom-host:9090/")
    assert get_api_base_url() == "http://custom-host:9090"


@pytest.mark.issue_23
def test_check_api_health_success() -> None:
    """check_api_health_callable returns JSON payload when status is ok."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "ok",
        "database": "connected",
        "app_env": "local",
    }

    with patch("httpx.get", return_value=mock_response) as mock_get:
        data = check_api_health_callable(api_url="http://test-api:8080")
        assert data["status"] == "ok"
        mock_get.assert_called_once_with("http://test-api:8080/health", timeout=10.0)


@pytest.mark.issue_23
def test_check_api_health_degraded_status() -> None:
    """check_api_health_callable raises RuntimeError when status is not ok."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "degraded",
        "database": "unreachable",
    }

    with (
        patch("httpx.get", return_value=mock_response),
        pytest.raises(RuntimeError, match="expected 'ok'"),
    ):
        check_api_health_callable(api_url="http://test-api:8080")


@pytest.mark.issue_23
def test_check_api_health_http_error() -> None:
    """check_api_health_callable raises HTTPStatusError when server responds with 503."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 503
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        message="Service Unavailable",
        request=MagicMock(spec=httpx.Request),
        response=mock_response,
    )

    with (
        patch("httpx.get", return_value=mock_response),
        pytest.raises(httpx.HTTPStatusError),
    ):
        check_api_health_callable(api_url="http://test-api:8080")


@pytest.mark.issue_23
def test_check_api_health_connection_error() -> None:
    """check_api_health_callable propagates network connection failures."""
    with (
        patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")),
        pytest.raises(httpx.ConnectError),
    ):
        check_api_health_callable(api_url="http://test-api:8080")


@pytest.mark.issue_23
def test_trigger_cycle_success() -> None:
    """trigger_cycle_callable dispatches POST request and returns summary."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "cycle_id": "cycle_abc123",
        "decisions": [{"decision_id": "dec_1"}],
        "orders": [{"order_id": "ord_1"}],
        "fills": [{"fill_id": "fill_1"}],
        "portfolio_state": {"total_equity": 105000.0},
    }

    with patch("httpx.post", return_value=mock_response) as mock_post:
        data = trigger_cycle_callable(api_url="http://test-api:8080")
        assert data["cycle_id"] == "cycle_abc123"
        mock_post.assert_called_once_with(
            "http://test-api:8080/cycles",
            json={},
            timeout=300.0,
        )


@pytest.mark.issue_23
def test_trigger_cycle_custom_watchlist() -> None:
    """trigger_cycle_callable supplies watchlist in JSON payload when provided."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "cycle_id": "cycle_custom",
        "watchlist": ["AAPL", "MSFT"],
        "portfolio_state": {"total_equity": 100000.0},
    }

    with patch("httpx.post", return_value=mock_response) as mock_post:
        data = trigger_cycle_callable(
            api_url="http://test-api:8080",
            watchlist=["AAPL", "MSFT"],
        )
        assert data["cycle_id"] == "cycle_custom"
        mock_post.assert_called_once_with(
            "http://test-api:8080/cycles",
            json={"watchlist": ["AAPL", "MSFT"]},
            timeout=300.0,
        )


@pytest.mark.issue_23
def test_trigger_cycle_http_error() -> None:
    """trigger_cycle_callable raises HTTPStatusError on 500 server error."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        message="Internal Server Error",
        request=MagicMock(spec=httpx.Request),
        response=mock_response,
    )

    with (
        patch("httpx.post", return_value=mock_response),
        pytest.raises(httpx.HTTPStatusError),
    ):
        trigger_cycle_callable(api_url="http://test-api:8080")


@pytest.mark.issue_23
def test_task_functions_execute() -> None:
    """Airflow @task functions invoke the underlying callables."""
    with (
        patch(
            "dags.trading_cycle_dag.check_api_health_callable",
            return_value={"status": "ok"},
        ) as mock_health,
        patch(
            "dags.trading_cycle_dag.trigger_cycle_callable",
            return_value={"cycle_id": "test_id"},
        ) as mock_cycle,
    ):
        res_health = check_api_health.function()
        assert res_health == {"status": "ok"}
        mock_health.assert_called_once()

        res_cycle = trigger_trading_cycle.function()
        assert res_cycle == {"cycle_id": "test_id"}
        mock_cycle.assert_called_once()
