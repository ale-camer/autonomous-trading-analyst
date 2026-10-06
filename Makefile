# =============================================================================
# autonomous-trading-analyst - project automation
# Every target calls the binaries in .venv/bin directly (no activation needed).
# Run `make` or `make help` to list all targets.
# =============================================================================

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:
.DEFAULT_GOAL := help

PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin
PY := $(BIN)/python
PIP := $(BIN)/pip
RUFF := $(BIN)/ruff
MYPY := $(BIN)/mypy
PYTEST := $(BIN)/pytest
PIP_AUDIT := $(BIN)/pip-audit
BANDIT := $(BIN)/bandit

PACKAGE := autonomous_trading_analyst
BASE_BRANCH := develop
MAIN_BRANCH := main
TYPE ?= feature

# Fails with a clear message when a required parameter is missing.
# Usage: $(call require,VAR_NAME,usage example)
define require
if [ -z "$(strip $($(1)))" ]; then echo 'ERROR: $(1) is required. Usage: $(2)' >&2; exit 1; fi
endef

# Fails when the virtual environment tools are not installed.
define require_venv
if [ ! -x "$(PYTEST)" ]; then echo "ERROR: tools not found in $(VENV). Run 'make venv deps' first." >&2; exit 1; fi
endef

.PHONY: help venv deps lint format typecheck check test test-unit test-integration \
	test-issue ci clean security start-issue finish-issue finish-milestone

##@ General

help: ## Show this help (default target)
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target> [VAR=value]\n"} \
		/^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0, 5)} \
		/^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

##@ Environment

venv: ## Create the .venv virtual environment (idempotent)
	@if [ -x "$(PY)" ]; then
		echo "$(VENV) already exists ($$($(PY) --version))"
	else
		$(PYTHON) -m venv $(VENV)
		echo "Created $(VENV) ($$($(PY) --version))"
	fi

deps: venv ## Install the package in editable mode with all extras + dev (needs network)
	$(PY) -m pip install --upgrade pip
	$(PIP) install -e ".[all,dev]"

##@ Quality

lint: ## Run ruff lint and format check
	@$(call require_venv)
	$(RUFF) check .
	$(RUFF) format --check .

format: ## Auto-format and auto-fix with ruff
	@$(call require_venv)
	$(RUFF) format .
	$(RUFF) check --fix .

typecheck: ## Run mypy (strict) on src
	@$(call require_venv)
	$(MYPY) src

check: lint typecheck ## Run lint + typecheck

security: ## Audit dependencies (pip-audit) and scan code (bandit) (needs network)
	@$(call require_venv)
	$(PIP_AUDIT) --skip-editable
	$(BANDIT) -c pyproject.toml -r src -q

##@ Tests

test: ## Run the whole test suite with coverage
	@$(call require_venv)
	$(PYTEST) --cov=$(PACKAGE) --cov-report=term-missing

test-unit: ## Run unit tests (tests/unit)
	@$(call require_venv)
	rc=0; $(PYTEST) tests/unit || rc=$$?
	if [ $$rc -eq 5 ]; then echo "No unit tests collected yet."; exit 0; fi
	exit $$rc

test-integration: ## Run integration tests (tests/integration)
	@$(call require_venv)
	rc=0; $(PYTEST) tests/integration || rc=$$?
	if [ $$rc -eq 5 ]; then echo "No integration tests collected yet."; exit 0; fi
	exit $$rc

test-issue: ## Run tests marked issue_<ID>; fails if none exist (ID=X)
	@$(call require,ID,make test-issue ID=X)
	if ! [[ "$(ID)" =~ ^[0-9]+$$ ]]; then echo "ERROR: ID must be a number, got '$(ID)'." >&2; exit 1; fi
	$(call require_venv)
	rc=0; $(PYTEST) -m "issue_$(ID)" || rc=$$?
	if [ $$rc -eq 5 ]; then
		echo "ERROR: no tests marked with @pytest.mark.issue_$(ID). Every issue must ship marked tests." >&2
		exit 1
	fi
	exit $$rc

ci: check test ## Run everything a CI pipeline runs (check + test)

##@ Maintenance

clean: ## Remove caches and build artifacts
	@rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage .coverage.* coverage.xml htmlcov build dist
	find . -path ./$(VENV) -prune -o -type d -name "__pycache__" -exec rm -rf {} +
	find . -path ./$(VENV) -prune -o -type d -name "*.egg-info" -exec rm -rf {} +
	echo "Clean."

##@ Issue lifecycle (git / GitHub: run by the user only)

start-issue: ## Create TYPE/issue-ID-NAME from develop (ID=X NAME=short-name [TYPE=feature|fix])
	@$(call require,ID,make start-issue ID=X NAME=short-name [TYPE=feature|fix])
	$(call require,NAME,make start-issue ID=X NAME=short-name [TYPE=feature|fix])
	if ! [[ "$(ID)" =~ ^[0-9]+$$ ]]; then echo "ERROR: ID must be a number, got '$(ID)'." >&2; exit 1; fi
	if ! [[ "$(NAME)" =~ ^[a-z0-9]+(-[a-z0-9]+)*$$ ]]; then echo "ERROR: NAME must be kebab-case, got '$(NAME)'." >&2; exit 1; fi
	case "$(TYPE)" in feature|fix) ;; *) echo "ERROR: TYPE must be 'feature' or 'fix', got '$(TYPE)'." >&2; exit 1 ;; esac
	if [ -n "$$(git status --porcelain)" ]; then echo "ERROR: working tree is not clean. Commit or stash first." >&2; exit 1; fi
	git checkout $(BASE_BRANCH)
	git pull --ff-only
	git checkout -b "$(TYPE)/issue-$(ID)-$(NAME)"
	echo "On branch $(TYPE)/issue-$(ID)-$(NAME)"

finish-issue: ## check, commit, push, squash-merge PR into develop, close issue (ID=X MSG="type(scope): msg")
	@$(call require,ID,make finish-issue ID=X MSG="type(scope): description")
	$(call require,MSG,make finish-issue ID=X MSG="type(scope): description")
	if ! [[ "$(ID)" =~ ^[0-9]+$$ ]]; then echo "ERROR: ID must be a number, got '$(ID)'." >&2; exit 1; fi
	cc_re='^(feat|fix|refactor|test|docs|chore|ci)(\([a-z0-9._/-]+\))?!?: .+$$'
	if ! [[ "$$MSG" =~ $$cc_re ]]; then echo "ERROR: MSG must follow Conventional Commits: type(scope): description" >&2; exit 1; fi
	branch="$$(git rev-parse --abbrev-ref HEAD)"
	branch_re='^(feature|fix)/issue-$(ID)-[a-z0-9-]+$$'
	if ! [[ "$$branch" =~ $$branch_re ]]; then
		echo "ERROR: current branch '$$branch' is not the branch of issue $(ID) (feature|fix/issue-$(ID)-...)." >&2
		exit 1
	fi
	$(MAKE) --no-print-directory check
	git add -A
	if git diff --cached --quiet; then
		echo "Nothing new to commit; pushing existing commits."
	else
		git commit -m "$$MSG"
	fi
	git push -u origin "$$branch"
	if [ "$(ID)" = "0" ]; then body="Day 0 setup (issue 0 is not tracked on GitHub)."; else body="Closes #$(ID)"; fi
	pr_url="$$(gh pr create --base $(BASE_BRANCH) --head "$$branch" --title "$$MSG" --body "$$body")"
	echo "PR: $$pr_url"
	gh pr merge "$$pr_url" --squash --delete-branch
	git checkout $(BASE_BRANCH)
	git pull --ff-only
	if git show-ref --verify --quiet "refs/heads/$$branch"; then git branch -D "$$branch"; fi
	if git ls-remote --exit-code --heads origin "$$branch" >/dev/null 2>&1; then git push origin --delete "$$branch"; fi
	if [ "$(ID)" != "0" ]; then
		if [ "$$(gh issue view $(ID) --json state -q .state)" = "OPEN" ]; then gh issue close $(ID); else echo "Issue #$(ID) already closed."; fi
	fi
	echo "Issue $(ID) finished. Now on $(BASE_BRANCH)."

finish-milestone: ## Merge develop into main (merge commit), tag and close milestone (MILESTONE=MX)
	@$(call require,MILESTONE,make finish-milestone MILESTONE=MX)
	if ! [[ "$(MILESTONE)" =~ ^M[0-9]+$$ ]]; then echo "ERROR: MILESTONE must look like M1, M2, ..., got '$(MILESTONE)'." >&2; exit 1; fi
	if [ -n "$$(git status --porcelain)" ]; then echo "ERROR: working tree is not clean." >&2; exit 1; fi
	git checkout $(BASE_BRANCH)
	git pull --ff-only
	pr_url="$$(gh pr create --base $(MAIN_BRANCH) --head $(BASE_BRANCH) --title "release: $(MILESTONE)" --body "Milestone $(MILESTONE): merge $(BASE_BRANCH) into $(MAIN_BRANCH).")"
	echo "PR: $$pr_url"
	gh pr merge "$$pr_url" --merge
	git fetch origin --tags
	git tag -a "$(MILESTONE)" "origin/$(MAIN_BRANCH)" -m "Milestone $(MILESTONE)"
	git push origin "$(MILESTONE)"
	number="$$(gh api 'repos/{owner}/{repo}/milestones?state=open&per_page=100' --jq '.[] | select(.title | startswith("$(MILESTONE) -")) | .number')"
	if [ -n "$$number" ]; then
		gh api -X PATCH "repos/{owner}/{repo}/milestones/$$number" -f state=closed >/dev/null
		echo "Milestone $(MILESTONE) closed on GitHub."
	else
		echo "WARNING: no open GitHub milestone titled '$(MILESTONE) - ...' was found." >&2
	fi
	git checkout $(BASE_BRANCH)
	git pull --ff-only
	echo "Milestone $(MILESTONE) released and tagged."
