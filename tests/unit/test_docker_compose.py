"""Unit tests validating Dockerfile, .dockerignore, init-db.sql, and docker-compose.yml."""

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def dockerfile_content() -> str:
    """Read the root Dockerfile."""
    dockerfile_path = REPO_ROOT / "Dockerfile"
    assert dockerfile_path.exists(), "Dockerfile does not exist in repo root"
    return dockerfile_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dockerignore_lines() -> set[str]:
    """Read .dockerignore rules."""
    dockerignore_path = REPO_ROOT / ".dockerignore"
    assert dockerignore_path.exists(), ".dockerignore does not exist in repo root"
    return {
        line.strip()
        for line in dockerignore_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


@pytest.fixture(scope="module")
def compose_data() -> dict[str, Any]:
    """Parse docker-compose.yml using PyYAML."""
    compose_path = REPO_ROOT / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml does not exist in repo root"
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "docker-compose.yml did not parse as a dictionary"
    return data


@pytest.mark.issue_24
def test_dockerfile_syntax_and_best_practices(dockerfile_content: str) -> None:
    """Dockerfile specifies base image, creates non-root user trader, and defines healthcheck."""
    assert "FROM python:3.12-slim" in dockerfile_content
    assert "apt-get install -y --no-install-recommends" in dockerfile_content
    assert "curl" in dockerfile_content
    assert "libpq-dev" in dockerfile_content

    # Non-root user creation matching AIRFLOW_UID (50000)
    assert "groupadd -g 50000 trader" in dockerfile_content
    assert "useradd -u 50000 -g trader" in dockerfile_content
    assert "USER trader" in dockerfile_content

    # Port and healthcheck
    assert "EXPOSE 8080" in dockerfile_content
    assert "HEALTHCHECK" in dockerfile_content
    assert "curl -f http://localhost:8080/health" in dockerfile_content
    assert "uvicorn" in dockerfile_content
    assert "autonomous_trading_analyst.api:app" in dockerfile_content


@pytest.mark.issue_24
def test_dockerignore_rules(dockerignore_lines: set[str]) -> None:
    """dockerignore excludes local virtualenvs, caches, git metadata, and environment files."""
    required_ignores = {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".coverage",
        ".env",
    }
    for rule in required_ignores:
        assert rule in dockerignore_lines, f"Expected rule '{rule}' not found in .dockerignore"


@pytest.mark.issue_24
def test_init_db_sql_script() -> None:
    """infra/init-db.sql provisions the pgvector extension and Airflow metadata database."""
    sql_path = REPO_ROOT / "infra" / "init-db.sql"
    assert sql_path.exists(), "infra/init-db.sql does not exist"

    content = sql_path.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS vector;" in content
    assert "CREATE DATABASE airflow;" in content
    assert "GRANT ALL PRIVILEGES ON DATABASE airflow TO trader;" in content


@pytest.mark.issue_24
def test_docker_compose_structure(compose_data: dict[str, Any]) -> None:
    """docker-compose.yml defines services and volumes top-level sections."""
    assert "services" in compose_data
    assert "volumes" in compose_data

    services = compose_data["services"]
    assert "db" in services
    assert "api" in services
    assert "airflow" in services


@pytest.mark.issue_24
def test_docker_compose_db_service(compose_data: dict[str, Any]) -> None:
    """db service uses pgvector/pgvector:pg16 with healthcheck and persistent storage."""
    db = compose_data["services"]["db"]
    assert db["image"] == "pgvector/pgvector:pg16"
    assert "postgres_data:/var/lib/postgresql/data" in db["volumes"]
    assert "./infra/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql:ro" in db["volumes"]

    # Healthcheck
    assert "healthcheck" in db
    test_cmd = " ".join(db["healthcheck"]["test"])
    assert "pg_isready" in test_cmd


@pytest.mark.issue_24
def test_docker_compose_api_service(compose_data: dict[str, Any]) -> None:
    """api service depends on healthy db and defines /health healthcheck."""
    api = compose_data["services"]["api"]
    assert api["build"]["dockerfile"] == "Dockerfile"
    assert api["depends_on"]["db"]["condition"] == "service_healthy"

    # Port mapping
    assert "8080:8080" in api["ports"]

    # Healthcheck
    assert "healthcheck" in api
    test_cmd = " ".join(api["healthcheck"]["test"])
    assert "http://localhost:8080/health" in test_cmd


@pytest.mark.issue_24
def test_docker_compose_airflow_service(compose_data: dict[str, Any]) -> None:
    """airflow service runs standalone, mounts dags, and depends on healthy api and db."""
    airflow = compose_data["services"]["airflow"]
    assert "standalone" in airflow["command"]
    assert airflow["depends_on"]["api"]["condition"] == "service_healthy"
    assert airflow["depends_on"]["db"]["condition"] == "service_healthy"

    # Airflow webserver port mapped deconflicted from API
    assert "8081:8080" in airflow["ports"]
    assert "./dags:/app/dags:ro" in airflow["volumes"]
    assert airflow["environment"]["AGENT_API_URL"] == "http://api:8080"


@pytest.mark.issue_24
def test_docker_compose_port_mappings_no_collision(compose_data: dict[str, Any]) -> None:
    """All published host ports across services are distinct and deconflicted."""
    published_ports: list[str] = []
    for config in compose_data["services"].values():
        ports = config.get("ports", [])
        for p in ports:
            host_port = str(p).split(":")[0]
            published_ports.append(host_port)

    # Published ports should be unique
    assert len(published_ports) == len(set(published_ports)), (
        f"Detected port collision in host port mappings: {published_ports}"
    )
    assert "5432" in published_ports
    assert "8080" in published_ports
    assert "8081" in published_ports


@pytest.mark.issue_24
def test_docker_compose_volumes(compose_data: dict[str, Any]) -> None:
    """Persistent named volumes for postgres and airflow data are defined."""
    volumes = compose_data["volumes"]
    assert "postgres_data" in volumes
    assert "airflow_data" in volumes


@pytest.mark.issue_24
def test_docker_compose_cli_validation() -> None:
    """Run docker compose config validation if docker CLI is available."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        pytest.skip("Docker CLI not installed on host")

    result = subprocess.run(  # noqa: S603
        [docker_bin, "compose", "config"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"docker compose config failed: {result.stderr}"
