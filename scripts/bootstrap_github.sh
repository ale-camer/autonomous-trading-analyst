#!/usr/bin/env bash
# =============================================================================
# Bootstrap the GitHub repository for autonomous-trading-analyst.
#
# Run ONCE by the user, from the repository root, after Day 0 scaffolding and
# BEFORE `make finish-issue ID=0 ...`:
#   1. creates the public repo and the `origin` remote,
#   2. pushes `main` and `develop`,
#   3. creates milestones M1-M5,
#   4. creates issues #1-#25 in roadmap order (docs/roadmap.md), each with its
#      milestone, aborting if GitHub numbering diverges from the roadmap.
# =============================================================================
set -euo pipefail

OWNER="ale-camer"
REPO_NAME="autonomous-trading-analyst"
REPO="${OWNER}/${REPO_NAME}"
DESCRIPTION="Autonomous ReAct trading analyst: decides BUY/SELL/HOLD, paper-trades with deterministic risk guardrails and learns from episodic memory (paper trading only)."

M1="M1 - Foundations & Market Tools"
M2="M2 - ReAct Agent Core"
M3="M3 - Risk, Paper Trading & Memory"
M4="M4 - Evaluation & Backtesting"
M5="M5 - Platform & Delivery"

die() { echo "ERROR: $*" >&2; exit 1; }

# ----------------------------------------------------------------- preflight
command -v gh >/dev/null || die "GitHub CLI 'gh' is not installed."
gh auth status >/dev/null 2>&1 || die "Not authenticated. Run 'gh auth login'."
[ -f Makefile ] && [ -f docs/roadmap.md ] || die "Run this script from the repository root."
git show-ref --verify --quiet refs/heads/main || die "Local branch 'main' does not exist."
git show-ref --verify --quiet refs/heads/develop || die "Local branch 'develop' does not exist."
if git remote get-url origin >/dev/null 2>&1; then die "Remote 'origin' already exists."; fi
if gh repo view "${REPO}" >/dev/null 2>&1; then die "Repository ${REPO} already exists."; fi

# ------------------------------------------------------------ repo + branches
echo "==> Creating public repository ${REPO}"
gh repo create "${REPO}" --public --source=. --remote=origin --description "${DESCRIPTION}"

echo "==> Pushing main and develop"
git push -u origin main
git push -u origin develop

# ----------------------------------------------------------------- milestones
create_milestone() {
  local title="$1" description="$2"
  gh api "repos/${REPO}/milestones" -f title="${title}" -f description="${description}" >/dev/null
  echo "    milestone: ${title}"
}

echo "==> Creating milestones"
create_milestone "${M1}" "CI, typed settings, domain models and all agent tools (market data, indicators, anomalies, P-09 research) behind interfaces with fakes, exposed via a tool registry."
create_milestone "${M2}" "Provider-agnostic LLM function calling with cost tracking, episode scratchpad and the explicit, traceable ReAct loop ending in a validated signal."
create_milestone "${M3}" "Deterministic risk guardrails, paper broker, full trace persistence, pgvector episodic memory with outcome reflection, and the end-to-end analysis cycle."
create_milestone "${M4}" "Point-in-time backtest of the agent vs buy & hold and an SMA-crossover rule: return, Sharpe, max drawdown, win rate and cost per decision."
create_milestone "${M5}" "FastAPI, Airflow scheduling, Docker Compose stack and a GCS artifact store provisioned with Terraform."

# --------------------------------------------------------------------- issues
create_issue() {
  local expected="$1" milestone="$2" title="$3" body="$4"
  local url number
  url="$(gh issue create --repo "${REPO}" --title "${title}" --milestone "${milestone}" --body "${body}")"
  number="${url##*/}"
  [ "${number}" = "${expected}" ] || die "Issue '${title}' got #${number}, expected #${expected}. Stop and fix numbering before any PR."
  echo "    #${number} ${title}"
}

echo "==> Creating issues"
create_issue 1 "${M1}" "CI workflow (GitHub Actions)" \
"GitHub Actions workflow that runs \`make ci\` (ruff, mypy strict, pytest) on pushes and PRs to \`main\` and \`develop\`, with pip caching. A test validates the workflow structure."

create_issue 2 "${M1}" "Settings & domain models" \
"Typed settings with pydantic-settings (\`TRADING_MODE\` restricted to \`paper\`, risk limits, budgets, watchlist) and Pydantic domain models: Action, Signal (size, confidence, rationale, citations), Order, Fill, Position, PortfolioState, TraceStep, DecisionRecord."

create_issue 3 "${M1}" "Market data provider (Yahoo + fake)" \
"\`MarketDataProvider\` interface returning validated OHLCV bars and latest prices, with a Yahoo Finance implementation (as in P-01) and a deterministic fake. Point-in-time queries (no data after an \`as_of\` date)."

create_issue 4 "${M1}" "Technical indicators" \
"Pure, tested indicator functions over OHLCV data: SMA, EMA, RSI, MACD, ATR and Bollinger Bands, plus a summary object suitable for an agent observation."

create_issue 5 "${M1}" "Anomaly signals (P-06 style)" \
"Rolling z-score anomaly detection on returns and volume (P-06 style), producing structured anomaly signals with severity for the agent."

create_issue 6 "${M1}" "P-09 research client" \
"\`ResearchClient\` interface for P-09 \`POST /research\` with an httpx implementation (timeouts, error mapping) and a fake, returning a validated research summary with sources."

create_issue 7 "${M1}" "Tool registry & JSON schemas" \
"\`Tool\` protocol and \`ToolRegistry\` exposing market data, indicators, anomalies and research as LLM tools with JSON schemas derived from Pydantic argument models, and safe dispatch returning structured observations or errors."

create_issue 8 "${M2}" "LLM client abstraction & fake" \
"Provider-agnostic \`LLMClient\` with normalized messages, tool definitions, tool calls and token usage, plus a scripted \`FakeLLMClient\` for deterministic agent tests."

create_issue 9 "${M2}" "LLM providers & cost tracking" \
"OpenAI, Anthropic and Gemini implementations of \`LLMClient\` (function calling), a provider factory from settings and a pricing table computing USD cost per call."

create_issue 10 "${M2}" "Scratchpad & trace recorder" \
"Per-episode scratchpad (short-term memory) recording thoughts, tool calls and observations with stable IDs, tokens and cost, exportable as a complete decision trace."

create_issue 11 "${M2}" "ReAct loop & signal contract" \
"Explicit ReAct loop (Thought -> Action -> Observation) with system prompt, step and cost budgets, error observations and a terminal \`submit_signal\` tool whose rationale must cite existing observation IDs."

create_issue 12 "${M3}" "Deterministic risk guardrails" \
"\`RiskManager\` enforcing max position size, max gross exposure, stop-loss, max trades per day, watchlist-only and no shorting/leverage. It approves, resizes or rejects orders with explicit reasons, outside the LLM."

create_issue 13 "${M3}" "Paper broker & portfolio accounting" \
"\`PaperBroker\` (the only broker) filling orders with slippage and commission, tracking cash, positions, realized/unrealized PnL and portfolio snapshots."

create_issue 14 "${M3}" "Decision & trace persistence" \
"SQLAlchemy schema and repositories for decisions, trace steps (thoughts, tool calls, observations, tokens, cost), orders, fills and portfolio snapshots on PostgreSQL."

create_issue 15 "${M3}" "Episodic memory with pgvector" \
"Embedding interface (provider + fake) and pgvector-backed episodic memory storing decision context and outcome, with similarity recall exposed to the agent as the \`recall_memory\` tool."

create_issue 16 "${M3}" "Outcome reflection" \
"Job that scores past decisions with realized forward returns over a horizon and writes the outcome back to episodic memory so future recalls include what happened next."

create_issue 17 "${M3}" "Analysis cycle orchestrator" \
"End-to-end cycle: watchlist -> agent -> risk -> paper broker -> persistence -> memory, plus a stop-loss sweep, returning a cycle summary. Runs fully offline with fakes in tests."

create_issue 18 "${M4}" "Performance metrics" \
"Metrics over an equity curve and trade list: total return, annualized Sharpe, max drawdown, win rate and LLM cost per decision."

create_issue 19 "${M4}" "Baseline strategies" \
"Baseline strategies on the same paper broker: buy & hold and an SMA-crossover technical rule."

create_issue 20 "${M4}" "Point-in-time backtest engine" \
"Backtest engine replaying historical dates without look-ahead, running the agent (real or fake LLM) and the baselines under the same risk limits and costs, collecting equity curves and decision costs."

create_issue 21 "${M4}" "Backtest report & CLI" \
"Markdown/JSON report comparing agent vs baselines (return, Sharpe, max drawdown, win rate, cost per decision) and a CLI entry point to run backtests."

create_issue 22 "${M5}" "FastAPI agent & portfolio API" \
"FastAPI app: \`POST /cycles\`, \`GET /portfolio\`, \`GET /decisions\`, \`GET /decisions/{id}\` (full trace) and \`GET /health\`, with dependency injection of fakes in tests."

create_issue 23 "${M5}" "Airflow trading-cycle DAG" \
"Airflow DAG that triggers analysis cycles on a schedule through \`POST /cycles\` (thin HTTP trigger), with DAG integrity tests."

create_issue 24 "${M5}" "Docker & Compose stack" \
"Dockerfile for the API and a Compose stack with PostgreSQL + pgvector, the API and Airflow, with healthchecks and env-file configuration."

create_issue 25 "${M5}" "GCS artifact store & Terraform" \
"\`ArtifactStore\` interface (local fake + Google Cloud Storage) for backtest reports and trace exports, and Terraform in \`infra/\` provisioning the GCS bucket."

echo "==> Done: ${REPO} with 5 milestones and 25 issues."
echo "    Next: make finish-issue ID=0 MSG=\"chore(setup): day 0 scaffolding\""
