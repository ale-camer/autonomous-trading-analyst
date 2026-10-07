"""Tests for GitHub Actions CI workflow configuration."""

from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"


@pytest.mark.issue_1
def test_ci_workflow_file_exists() -> None:
    """The CI workflow file must exist."""
    assert WORKFLOW_PATH.is_file(), f"Workflow file not found at {WORKFLOW_PATH}"


@pytest.mark.issue_1
def test_ci_workflow_valid_yaml_and_triggers() -> None:
    """The CI workflow must be valid YAML and trigger on main and develop branches."""
    assert WORKFLOW_PATH.is_file()
    with WORKFLOW_PATH.open("r", encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)

    assert isinstance(data, dict), "CI workflow must be a valid YAML mapping"

    # PyYAML parses unquoted 'on:' as boolean True (YAML 1.1 specification)
    triggers = data.get("on") if "on" in data else data.get(True)
    assert isinstance(triggers, dict), "Workflow must declare trigger events mapping"

    assert "push" in triggers, "Workflow must trigger on push"
    assert "pull_request" in triggers, "Workflow must trigger on pull_request"

    push_branches = triggers["push"].get("branches", [])
    pr_branches = triggers["pull_request"].get("branches", [])

    assert "main" in push_branches
    assert "develop" in push_branches
    assert "main" in pr_branches
    assert "develop" in pr_branches


@pytest.mark.issue_1
def test_ci_workflow_jobs_and_steps() -> None:
    """The CI workflow must run on ubuntu-latest and execute make ci with Python 3.12."""
    with WORKFLOW_PATH.open("r", encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)

    assert "jobs" in data
    assert "ci" in data["jobs"]
    ci_job = data["jobs"]["ci"]

    assert ci_job.get("runs-on") == "ubuntu-latest"

    steps = ci_job.get("steps", [])
    assert isinstance(steps, list)
    assert len(steps) >= 3

    # Check checkout step
    has_checkout = any(
        "checkout" in step.get("uses", "") for step in steps if isinstance(step, dict)
    )
    assert has_checkout, "Workflow must contain a checkout step"

    # Check setup-python step with 3.12
    python_step = next(
        (
            step
            for step in steps
            if isinstance(step, dict) and "setup-python" in step.get("uses", "")
        ),
        None,
    )
    assert python_step is not None, "Workflow must contain setup-python step"
    assert python_step.get("with", {}).get("python-version") == "3.12"

    # Check dependency install and make ci
    step_runs = [step.get("run", "") for step in steps if isinstance(step, dict) and "run" in step]
    assert any("make deps" in run for run in step_runs), (
        "Workflow must install dependencies with make deps"
    )
    assert any("make ci" in run for run in step_runs), "Workflow must run make ci"
