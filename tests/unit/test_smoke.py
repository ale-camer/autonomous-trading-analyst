"""Smoke test: the package is importable and exposes its version."""

import pytest

import autonomous_trading_analyst


@pytest.mark.issue_0
def test_package_imports_and_exposes_version() -> None:
    assert isinstance(autonomous_trading_analyst.__version__, str)
    assert autonomous_trading_analyst.__version__
