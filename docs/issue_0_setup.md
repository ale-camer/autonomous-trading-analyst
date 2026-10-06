# Issue 0: Day 0 Project Setup & Scaffolding

**Branch**: `feature/issue-0-setup`
**Status**: Done
**PR**: opened by `make finish-issue` → `develop` (no "Closes": issue 0 does not exist on GitHub)
**Milestone**: M0 - Project Setup

## Objective
Create the empty, fully automated skeleton of `autonomous-trading-analyst` (Python package `autonomous_trading_analyst`): git flow branches, isolated `.venv`, complete self-documented `Makefile`, `pyproject.toml` with strict tooling, empty folder structure, a smoke test, the living workflow rules, the architecture draft, the roadmap and the GitHub bootstrap script. No business logic is written in this issue.

## Acceptance Criteria
- [x] Repository initialized with permanent branches `main` and `develop`, and work happens on `feature/issue-0-setup`
- [x] `.gitignore` excludes `.venv/`, `.env`, caches, build artifacts, Terraform state and local data/report outputs
- [x] `.env.example` documents every setting the project will need (LLM, embeddings, database, P-09 research API, watchlist, risk limits, paper broker, agent budgets, GCP) with safe placeholder values and `TRADING_MODE=paper`
- [x] `pyproject.toml` defines package `autonomous_trading_analyst` (src layout, Python >= 3.12), optional-dependency groups `dev`, `tools`, `llm`, `memory`, `api`, `orchestration`, `cloud` and `all` (union of all layer groups)
- [x] `pyproject.toml` configures ruff (lint + format), mypy (`strict = true`) and pytest (`--strict-markers`, marker `issue_0` registered)
- [x] Empty structure exists: `src/autonomous_trading_analyst/` (only `__init__.py` with `__version__` and `py.typed`), `dags/`, `tests/unit/`, `tests/integration/`, `infra/`, `docs/`, `scripts/` (with `.gitkeep` where empty)
- [x] `tests/unit/test_smoke.py` only imports the package and checks `__version__` (marked `@pytest.mark.issue_0`)
- [x] `Makefile` is complete and self-documented (`help` is the default target) with lifecycle targets (`start-issue`, `finish-issue`, `finish-milestone`) validating their parameters, and environment/quality targets (`venv`, `deps`, `lint`, `format`, `typecheck`, `check`, `test`, `test-unit`, `test-integration`, `test-issue`, `ci`, `clean`, `security`), all calling `.venv/bin/` binaries directly
- [x] `.venv` created with `make venv` and dependencies installed with `make deps`
- [x] `.agents/rules/workflow.md` reflects rules 2 to 11 (git flow, Conventional Commits, two-phase cycle, issue format, Makefile, language, autonomy, who runs what, quality gate, communication, internal plans)
- [x] `README.md` draft describes the proposed architecture (ReAct loop, tools, memory, risk guardrails, paper broker, evaluation, platform) with a Mermaid diagram
- [x] `docs/roadmap.md` contains the milestone → issues table (5 milestones, 25 issues) marking which issue closes each milestone
- [x] `scripts/bootstrap_github.sh` creates the public repo `ale-camer/autonomous-trading-analyst`, pushes `main` and `develop`, and creates all milestones and issues #1–#25 (with milestone assigned) in roadmap order, aborting if numbering diverges
- [x] `make check` and `make test-issue ID=0` pass

## Implementation Tasks

### 1. Preparation & Branching
Run by the user (PASO CERO; the Makefile does not exist yet):
```bash
cd ~/Projects/autonomous-trading-analysis
git init -b main
git commit --allow-empty -m "chore: initial commit"
git checkout -b develop
git checkout -b feature/issue-0-setup
```

### 2. Git Ignore Rules
- **File**: `.gitignore`
- **Change**: Ignore `.venv/`, `.env`, `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`, `htmlcov/`, `build/`, `dist/`, `*.egg-info/`, `.idea/`, `.vscode/`, `infra/**/.terraform/`, `*.tfstate*`, `*.tfvars` (except `*.tfvars.example`), `data/`, `reports/`, `logs/`, Airflow local files (`airflow.db`, `airflow-webserver.pid`).

### 3. Environment Template
- **File**: `.env.example`
- **Change**: Placeholder-only variables grouped by concern:
  - Runtime: `APP_ENV=local`, `LOG_LEVEL=INFO`, `TRADING_MODE=paper` (the only accepted value; documented as such).
  - LLM: `LLM_PROVIDER=fake|openai|anthropic|gemini`, `LLM_MODEL`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`.
  - Embeddings: `EMBEDDING_PROVIDER=fake|openai|gemini`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`.
  - Database: `DATABASE_URL=postgresql+psycopg://trader:trader@localhost:5432/trading`.
  - Tools: `RESEARCH_API_URL=http://localhost:8000` (P-09 `POST /research`), `RESEARCH_API_TIMEOUT_S`, `MARKET_DATA_PROVIDER=yahoo|fake`, `WATCHLIST=AAPL,MSFT,NVDA,SPY`.
  - Risk limits: `RISK_MAX_POSITION_PCT=0.10`, `RISK_MAX_GROSS_EXPOSURE_PCT=0.80`, `RISK_STOP_LOSS_PCT=0.08`, `RISK_MAX_TRADES_PER_DAY=5`.
  - Paper broker: `PAPER_INITIAL_CASH=100000`, `PAPER_COMMISSION_BPS=1`, `PAPER_SLIPPAGE_BPS=5`.
  - Agent budgets: `AGENT_MAX_STEPS=8`, `AGENT_MAX_COST_USD_PER_DECISION=0.05`, `MEMORY_TOP_K=5`.
  - GCP: `GCP_PROJECT_ID`, `GCP_REGION=europe-west1`, `GCS_ARTIFACTS_BUCKET`, `GOOGLE_APPLICATION_CREDENTIALS`.
  - Orchestration: `AGENT_API_URL=http://api:8080`, `AIRFLOW_UID=50000`.

### 4. Project Metadata & Tooling
- **File**: `pyproject.toml`
- **Change**:
  - `[build-system]` setuptools; `[project]` name `autonomous-trading-analyst`, version `0.1.0`, `requires-python = ">=3.12"`, core deps `pydantic>=2`, `pydantic-settings>=2`.
  - `[project.optional-dependencies]`:
    - `dev`: `ruff`, `mypy`, `pytest`, `pytest-cov`, `pyyaml`, `types-PyYAML`, `pip-audit`, `bandit`.
    - `tools`: `yfinance`, `pandas`, `numpy`, `httpx`.
    - `llm`: `openai`, `anthropic`, `google-genai`.
    - `memory`: `sqlalchemy>=2`, `psycopg[binary]>=3`, `pgvector`.
    - `api`: `fastapi`, `uvicorn[standard]`.
    - `orchestration`: `apache-airflow>=3,<4`.
    - `cloud`: `google-cloud-storage`.
    - `all`: self-referencing union `autonomous-trading-analyst[tools,llm,memory,api,orchestration,cloud]`.
  - `[tool.setuptools.packages.find]` with `where = ["src"]`; package data includes `py.typed`.
  - `[tool.ruff]`: `line-length = 100`, `target-version = "py312"`, `src = ["src", "tests"]`; lint `select = ["E", "F", "W", "I", "UP", "B", "SIM", "N", "S", "RUF"]`; `per-file-ignores` for `tests/**` → `S101`; format with double quotes.
  - `[tool.mypy]`: `strict = true`, `python_version = "3.12"`, `files = ["src"]`, `plugins = ["pydantic.mypy"]`.
  - `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `addopts = "-ra --strict-markers --strict-config"`, `markers = ["issue_0: Day 0 setup and scaffolding"]`.
  - `[tool.coverage.run]`: `source = ["autonomous_trading_analyst"]`.

### 5. Package & Folder Skeleton
- **File**: `src/autonomous_trading_analyst/__init__.py`, `src/autonomous_trading_analyst/py.typed`, `dags/.gitkeep`, `tests/unit/.gitkeep`, `tests/integration/.gitkeep`, `infra/.gitkeep`
- **Change**: `__init__.py` contains only the module docstring and `__version__ = "0.1.0"`; `py.typed` is an empty PEP 561 marker; `.gitkeep` files keep empty directories tracked. No sub-modules are created (they are created by the issue that implements them).

### 6. Smoke Test
- **File**: `tests/unit/test_smoke.py`
- **Change**: One test marked `@pytest.mark.issue_0` that imports `autonomous_trading_analyst` and asserts `__version__` is a non-empty string.

### 7. Self-Documented Makefile
- **File**: `Makefile`
- **Change**: Complete Makefile with `.DEFAULT_GOAL := help`, `SHELL := /bin/bash`, `.ONESHELL`, variables `VENV := .venv`, `PY`, `PIP`, `RUFF`, `MYPY`, `PYTEST`, `PIP_AUDIT`, `BANDIT` pointing to `$(VENV)/bin/`, and `## description` comments parsed by `help` (grep + awk).
  - `help`: lists every target with its description.
  - `venv`: `python3 -m venv .venv` (idempotent) and upgrades pip.
  - `deps`: `$(PIP) install -e ".[all,dev]"` (needs network).
  - `lint`: `ruff check .` + `ruff format --check .`. `format`: `ruff format .` + `ruff check --fix .`.
  - `typecheck`: `mypy src`. `check`: `lint` + `typecheck`.
  - `test`: full suite with coverage. `test-unit`: `tests/unit`. `test-integration`: `tests/integration`.
  - `test-issue ID=X`: validates `ID`, runs `pytest -m issue_$(ID)`; fails with a clear message when no test is marked (pytest exit code 5 is surfaced as an error).
  - `ci`: `check` + `test`. `security`: `pip-audit` + `bandit -r src -q`.
  - `clean`: removes `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `__pycache__`, `.coverage`, `htmlcov`, `build/`, `dist/`, `*.egg-info`.
  - `start-issue ID=X NAME=short-name [TYPE=feature|fix]`: validates params and `TYPE`, aborts on a dirty tree, `git checkout develop` → `git pull --ff-only` → `git checkout -b $(TYPE)/issue-$(ID)-$(NAME)`.
  - `finish-issue ID=X MSG="type(scope): description"`: validates params and Conventional Commit format of `MSG`, verifies the current branch matches `^(feature|fix)/issue-$(ID)-` → `make check` → `git add -A` → `git commit -m "$(MSG)"` → `git push -u origin <branch>` → `gh pr create --base develop --title "$(MSG)" --body "Closes #$(ID)"` (body without "Closes" when `ID=0`) → `gh pr merge --squash --delete-branch` → delete local branch if still present → `gh issue close $(ID)` (skipped when `ID=0`) → `git checkout develop` → `git pull --ff-only`.
  - `finish-milestone MILESTONE=MX`: validates param, `gh pr create --base main --head develop --title "release: $(MILESTONE)"` → `gh pr merge --merge` (merge commit, no squash) → `git fetch origin` → `git tag -a $(MILESTONE) origin/main -m "$(MILESTONE)"` → `git push origin $(MILESTONE)` → closes the GitHub milestone whose title starts with `$(MILESTONE) -` via `gh api` (PATCH `state=closed`) → `git checkout develop` → `git pull --ff-only`.

### 8. Virtual Environment & Dependencies
- **File**: `.venv/` (not tracked)
- **Change**: Run `make venv` and then `make deps` (requires network; permission will be requested explicitly before running it). Verify `.venv/bin/python --version` is >= 3.12 and the package imports in editable mode.

### 9. Living Workflow Rules
- **File**: `.agents/rules/workflow.md`
- **Change**: English document covering, one section each: virtual environments (`.venv`, Makefile uses `.venv/bin/`), git flow (`main`/`develop`, issue branches, squash to `develop`, merge commit to `main` per milestone), Conventional Commits, two-phase cycle (Phase A plan only → `start-issue` → Phase B implementation → `finish-issue` → `finish-milestone` when applicable; no next Phase A until confirmed), mandatory issue file format (verbatim template from rule 4.B, real numbering of N+1..N+3), Makefile & `pyproject.toml` conventions (markers per issue, `--strict-markers`), English-only, autonomy & `## Decisions`, who executes what (user: anything that changes git/GitHub state; agent: read-only git + verification commands; ask before network), quality gate (`make check` + `make test-issue ID=X` green, no unjustified `noqa`/`type: ignore`), communication formats (Phase A / Phase B reports), internal plans (issue file is the single source of truth), and a note that this file is updated in the same issue where the workflow changes.

### 10. README Architecture Draft
- **File**: `README.md`
- **Change**: Draft with: purpose and **paper-trading-only** disclaimer; relation to P-01/P-06/P-09; Mermaid architecture diagram; planned module layout; quickstart via Makefile; project status pointing to `docs/roadmap.md`. Proposed architecture:
  - `config.py`: typed settings (pydantic-settings); `TRADING_MODE` restricted to `paper`.
  - `domain/`: Pydantic models (`Action`, `Signal` with size/confidence/rationale/citations, `Order`, `Fill`, `Position`, `PortfolioState`, `TraceStep`, `DecisionRecord`).
  - `tools/`: `MarketDataProvider` (Yahoo + fake), technical indicators, P-06-style anomaly signals, P-09 `POST /research` client (+ fake), and a `ToolRegistry` that exposes each tool to the LLM with a JSON schema derived from Pydantic args.
  - `llm/`: provider-agnostic `LLMClient` with normalized messages/tool calls/usage (OpenAI, Anthropic, Gemini, scripted `FakeLLMClient`) and a pricing table for cost per call.
  - `agent/`: explicit ReAct loop (Thought → Action → Observation) with a per-episode scratchpad (short-term memory), step/cost budgets and a terminal `submit_signal` tool whose rationale must cite observation IDs.
  - `memory/`: episodic long-term memory (decision context + outcome) stored in PostgreSQL/pgvector, recalled by similarity through a `recall_memory` tool; outcome reflection writes realized results back.
  - `risk/`: deterministic `RiskManager` outside the LLM (max position size, max gross exposure, stop-loss, max trades/day, watchlist-only, no shorting/leverage) that approves, resizes or rejects orders.
  - `broker/`: `PaperBroker` only (slippage + commission, cash/positions/PnL); no live broker interface exists by design.
  - `persistence/`: SQLAlchemy schema and repositories for decisions, full traces (thoughts, tool calls, observations, tokens, cost), orders and portfolio snapshots.
  - `cycle.py`: analysis cycle (watchlist → agent → risk → broker → persist → stop-loss sweep).
  - `evaluation/`: point-in-time backtest of the agent vs buy & hold and an SMA-crossover rule; metrics (total return, Sharpe, max drawdown, win rate, cost per decision) and reports.
  - `api/`: FastAPI (`POST /cycles`, `GET /portfolio`, `GET /decisions`, `GET /decisions/{id}`, `GET /health`).
  - Platform: `dags/` Airflow DAG triggering cycles via the API, Docker Compose (api + Postgres/pgvector + Airflow), GitHub Actions CI, GCS artifact store provisioned with Terraform in `infra/`.

### 11. Roadmap
- **File**: `docs/roadmap.md`
- **Change**: Table `Milestone | Issue | Title | Branch | Closes milestone`, with the GitHub issue number equal to the roadmap number:
  - **M1 - Foundations & Market Tools**: #1 CI workflow (GitHub Actions), #2 Settings & domain models, #3 Market data provider (Yahoo + fake), #4 Technical indicators, #5 Anomaly signals (P-06 style), #6 P-09 research client, #7 Tool registry & JSON schemas ← closes M1.
  - **M2 - ReAct Agent Core**: #8 LLM client abstraction & fake, #9 LLM providers & cost tracking, #10 Scratchpad & trace recorder, #11 ReAct loop & signal contract ← closes M2.
  - **M3 - Risk, Paper Trading & Memory**: #12 Deterministic risk guardrails, #13 Paper broker & portfolio accounting, #14 Decision & trace persistence, #15 Episodic memory with pgvector, #16 Outcome reflection, #17 Analysis cycle orchestrator ← closes M3.
  - **M4 - Evaluation & Backtesting**: #18 Performance metrics, #19 Baseline strategies, #20 Point-in-time backtest engine, #21 Backtest report & CLI ← closes M4.
  - **M5 - Platform & Delivery**: #22 FastAPI agent & portfolio API, #23 Airflow trading-cycle DAG, #24 Docker & Compose stack, #25 GCS artifact store & Terraform ← closes M5.

### 12. GitHub Bootstrap Script
- **File**: `scripts/bootstrap_github.sh`
- **Change**: Executable bash script (`set -euo pipefail`), run by the user only: checks `gh auth status` and that `main`/`develop` exist locally; aborts if `ale-camer/autonomous-trading-analyst` already exists; `gh repo create ale-camer/autonomous-trading-analyst --public --source=. --remote=origin --description "..."`; `git push -u origin main develop`; creates milestones M1–M5 (title + description) via `gh api repos/{owner}/{repo}/milestones`; creates issues #1–#25 in roadmap order with `gh issue create --title --body --milestone`, parsing each returned URL and aborting if the number differs from the expected roadmap number; prints a final summary.

### 13. Verification & Quality Gates
```bash
make test-issue ID=0
make check
```

### 14. Git & Issue Finish
Run by the user (bootstrap first, so GitHub issue numbers are reserved before the first PR):
```bash
bash scripts/bootstrap_github.sh
make finish-issue ID=0 MSG="chore(setup): day 0 scaffolding"
```

## Decisions
- Issue 0 uses a local-only `M0 - Project Setup` label: it is not created on GitHub, so it never closes a milestone and has no Milestone Finish step.
- The local folder stays `autonomous-trading-analysis`; the GitHub repo name `autonomous-trading-analyst` is set explicitly in the bootstrap script, so the mismatch has no effect.
- CI is issue #1 so that `main`/`develop` are protected by `make ci` from the very first feature PR.
- Python >= 3.12 and src layout with `py.typed`: modern typing for mypy strict and no accidental imports from the repo root.
- Layer groups (`tools`, `llm`, `memory`, `api`, `orchestration`, `cloud`) mirror the architecture so each image/job can install only what it needs; `all` keeps local dev and CI complete.
- `apache-airflow` lives in the `orchestration` group so DAG integrity tests can run in CI; if it conflicts with the API/memory stack when installed, the fallback (image-only install) is decided and recorded in issue #23.
- The DAG will be a thin HTTP trigger of `POST /cycles`: business logic stays in the package and the API, not in Airflow.
- `S101` (assert) is ignored only under `tests/**` via `per-file-ignores`: pytest relies on `assert`; no inline `noqa` needed.
- `security` target is included (`pip-audit` + `bandit`): the project calls external APIs and handles API keys.
- Paper-only is enforced structurally: `TRADING_MODE` accepts only `paper` and no live-broker interface will exist.
- The risk layer is deterministic and runs after the LLM: the agent proposes, `RiskManager` disposes, so guardrails cannot be bypassed by prompting.
- GCP service: Cloud Storage (backtest reports and trace exports) provisioned with Terraform: cheapest useful service, abstracted behind an `ArtifactStore` with a local fake.
