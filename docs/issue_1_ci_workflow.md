# Issue 1: CI Workflow (GitHub Actions)

**Branch**: `feature/issue-1-ci-workflow`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (Closes #1)
**Milestone**: M1 - Foundations & Market Tools

## Objective
Configure GitHub Actions continuous integration (`.github/workflows/ci.yml`) to automatically validate code formatting, linting, type checks, and tests via `make ci` on every push and pull request targeting `main` and `develop`.

## Acceptance Criteria
- [x] `.github/workflows/ci.yml` triggers on `push` and `pull_request` against `main` and `develop` branches
- [x] CI workflow provisions Ubuntu with Python 3.12, uses pip caching, sets up the virtual environment (`make venv` and `make deps`), and executes `make ci`
- [x] `tests/unit/test_ci.py` validates workflow YAML syntax, triggers, and execution steps (marked `@pytest.mark.issue_1`)
- [x] `pyproject.toml` registers the `issue_1` marker
- [x] `make check` and `make test-issue ID=1` pass

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=1 NAME=ci-workflow
```

### 2. GitHub Actions CI Workflow
- **File**: `.github/workflows/ci.yml`
- **Change**: Define the CI pipeline workflow with trigger events on `push` and `pull_request` for `main` and `develop` branches. Configure the job to run on `ubuntu-latest`, setup Python 3.12 with pip cache, create `.venv`, install dependencies with `make deps`, and execute `make ci`.

### 3. CI Workflow Unit Tests
- **File**: `tests/unit/test_ci.py`
- **Change**: Implement unit tests parsing `.github/workflows/ci.yml` using `pyyaml` (`yaml.safe_load`) to assert file existence, valid syntax, trigger branches/events, Python version (3.12), and presence of the `make ci` step. Mark tests with `@pytest.mark.issue_1`.

### 4. Pytest Marker Registration
- **File**: `pyproject.toml`
- **Change**: Register the `issue_1` marker (`issue_1: CI workflow (GitHub Actions)`) under `[tool.pytest.ini_options]` `markers`.

### 5. Verification & Quality Gates
```bash
make test-issue ID=1
make check
```

### 6. Git & Issue Finish
```bash
make finish-issue ID=1 MSG="ci(workflow): add github actions ci workflow"
```

## Decisions
- Run `make ci` directly in GitHub Actions rather than re-declaring lint/test commands, ensuring total parity between local developer checks and remote CI.
- Validate the CI workflow YAML file via unit test with `pyyaml` (covered under `dev` dependencies) so regressions in workflow structure are caught locally before pushing.
- Allow untracked files in `make start-issue` via `--untracked-files=no` so Phase A planning documents do not block creating the issue branch.
