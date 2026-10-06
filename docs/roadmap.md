# Roadmap

Source of truth for milestones and issues. The GitHub issue number equals the roadmap number
(all issues are created by `scripts/bootstrap_github.sh` before the first PR). The issue marked
in **Closes milestone** is the last one of its milestone: its plan includes
`make finish-milestone MILESTONE=MX`.

Issue 0 (`feature/issue-0-setup`, Day 0 scaffolding) is local only and is not tracked on GitHub.

| Milestone | Issue | Title | Branch | Closes milestone |
|---|---|---|---|---|
| M1 - Foundations & Market Tools | #1 | CI workflow (GitHub Actions) | `feature/issue-1-ci-workflow` | |
| M1 - Foundations & Market Tools | #2 | Settings & domain models | `feature/issue-2-settings-domain-models` | |
| M1 - Foundations & Market Tools | #3 | Market data provider (Yahoo + fake) | `feature/issue-3-market-data-provider` | |
| M1 - Foundations & Market Tools | #4 | Technical indicators | `feature/issue-4-technical-indicators` | |
| M1 - Foundations & Market Tools | #5 | Anomaly signals (P-06 style) | `feature/issue-5-anomaly-signals` | |
| M1 - Foundations & Market Tools | #6 | P-09 research client | `feature/issue-6-research-client` | |
| M1 - Foundations & Market Tools | #7 | Tool registry & JSON schemas | `feature/issue-7-tool-registry` | ✅ M1 |
| M2 - ReAct Agent Core | #8 | LLM client abstraction & fake | `feature/issue-8-llm-client` | |
| M2 - ReAct Agent Core | #9 | LLM providers & cost tracking | `feature/issue-9-llm-providers` | |
| M2 - ReAct Agent Core | #10 | Scratchpad & trace recorder | `feature/issue-10-scratchpad-trace` | |
| M2 - ReAct Agent Core | #11 | ReAct loop & signal contract | `feature/issue-11-react-loop` | ✅ M2 |
| M3 - Risk, Paper Trading & Memory | #12 | Deterministic risk guardrails | `feature/issue-12-risk-guardrails` | |
| M3 - Risk, Paper Trading & Memory | #13 | Paper broker & portfolio accounting | `feature/issue-13-paper-broker` | |
| M3 - Risk, Paper Trading & Memory | #14 | Decision & trace persistence | `feature/issue-14-decision-persistence` | |
| M3 - Risk, Paper Trading & Memory | #15 | Episodic memory with pgvector | `feature/issue-15-episodic-memory` | |
| M3 - Risk, Paper Trading & Memory | #16 | Outcome reflection | `feature/issue-16-outcome-reflection` | |
| M3 - Risk, Paper Trading & Memory | #17 | Analysis cycle orchestrator | `feature/issue-17-analysis-cycle` | ✅ M3 |
| M4 - Evaluation & Backtesting | #18 | Performance metrics | `feature/issue-18-performance-metrics` | |
| M4 - Evaluation & Backtesting | #19 | Baseline strategies | `feature/issue-19-baseline-strategies` | |
| M4 - Evaluation & Backtesting | #20 | Point-in-time backtest engine | `feature/issue-20-backtest-engine` | |
| M4 - Evaluation & Backtesting | #21 | Backtest report & CLI | `feature/issue-21-backtest-report` | ✅ M4 |
| M5 - Platform & Delivery | #22 | FastAPI agent & portfolio API | `feature/issue-22-fastapi-app` | |
| M5 - Platform & Delivery | #23 | Airflow trading-cycle DAG | `feature/issue-23-airflow-dag` | |
| M5 - Platform & Delivery | #24 | Docker & Compose stack | `feature/issue-24-docker-compose` | |
| M5 - Platform & Delivery | #25 | GCS artifact store & Terraform | `feature/issue-25-gcs-terraform` | ✅ M5 |

## Milestones

- **M1 - Foundations & Market Tools**: CI, typed settings, domain models and every agent tool
  (market data, indicators, anomalies, P-09 research) exposed through a tool registry, each
  behind an interface with a fake.
- **M2 - ReAct Agent Core**: provider-agnostic LLM function calling with cost tracking, the
  episode scratchpad and the explicit, traceable ReAct loop that ends in a validated signal.
- **M3 - Risk, Paper Trading & Memory**: deterministic guardrails, the paper broker, full trace
  persistence, pgvector episodic memory with outcome reflection, and the end-to-end cycle.
- **M4 - Evaluation & Backtesting**: point-in-time backtest of the agent against buy & hold and
  an SMA-crossover rule with return, Sharpe, max drawdown, win rate and cost per decision.
- **M5 - Platform & Delivery**: FastAPI, Airflow scheduling, Docker Compose stack, and a GCS
  artifact store provisioned with Terraform.
