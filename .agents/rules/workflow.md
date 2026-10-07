# Workflow Rules (living document)

These rules apply for the whole life of the project, from issue 0 to the last milestone.
If the way of working changes, this file is updated **in the same issue** where the change
happens, and the change is recorded in that issue's `## Decisions` section.

## 1. Virtual environment
- The project uses an isolated virtual environment in `.venv` (`make venv` → `python3 -m venv .venv`).
- Every Makefile target calls the binaries in `.venv/bin/` directly, so nothing depends on the
  environment being activated.
- Dependencies are installed with `make deps` (`pip install -e ".[all,dev]"`, needs network).

## 2. Git flow
- Two permanent branches: `main` (production, always green) and `develop` (integration).
- Nobody works directly on `main` or `develop`.
- One branch per issue, created from `develop`: `feature/issue-X-short-name` or
  `fix/issue-X-short-name`.
- Issue branches are merged into `develop` through a PR with **squash merge**.
- Only `develop` is merged into `main`, when a milestone closes, with a **merge commit**
  (no squash) so the branches do not diverge. The merge is tagged `MX`.
- GitHub issues and PRs share numbering: all issues are created by
  `scripts/bootstrap_github.sh` before the first PR, so roadmap issue X is GitHub issue #X.

## 3. Conventional Commits
- Every commit message follows `type(scope): description`.
- Allowed types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`.
- `make finish-issue` rejects messages that do not match this format.

## 4. Two-phase cycle per issue
1. **Phase A - Plan**: the user writes "Hacé el plan para el issue X". The agent ONLY creates
   `docs/issue_X_name.md` (Status: Planned). No code, no other files.
2. The user runs `make start-issue ID=X NAME=short-name`.
3. **Phase B - Implementation**: the user writes "Hacé los puntos del 2 al N de
   docs/issue_X_name.md". The agent:
   - sets Status to In Progress;
   - implements ONLY those points (anything out of scope goes to `## Decisions` or is proposed
     as a new issue);
   - ALWAYS runs point N+1 (Verification & Quality Gates), even if not in the requested range;
   - ticks the satisfied Acceptance Criteria, sets Status to Done and reports.
4. The user runs `make finish-issue ID=X MSG="type(scope): description"`.
5. If the issue is the last one of its milestone (see `docs/roadmap.md`), the plan includes
   step N+3 with `make finish-milestone MILESTONE=MX`, and the agent reminds the user in the
   Phase B report.
6. The agent does NOT start Phase A of the next issue until the user confirms that
   `finish-issue` (and `finish-milestone`, when applicable) was run.

Issue 0 exception: the Makefile does not exist yet, so point 1 lists the initial git commands
instead of `make start-issue`.

## 5. Mandatory issue file format
Every `docs/issue_X_name.md` (including issue 0) uses exactly this structure, with no extra or
renamed sections:

````markdown
# Issue X: [Issue Name]

**Branch**: `feature/issue-X-short-name`
**Status**: Planned | In Progress | Done
**PR**: opened by `make finish-issue` → `develop` (Closes #X)
**Milestone**: MX - [Milestone Name]

## Objective
[One or two sentences: what this issue delivers and why.]

## Acceptance Criteria
- [ ] `src/<pkg>/<module>.py` exposes `<function/class>` that ...
- [ ] `tests/unit/test_<module>.py` covers ... (marked `@pytest.mark.issue_X`)
- [ ] `pyproject.toml` registers the `issue_X` marker
- [ ] `make check` and `make test-issue ID=X` pass

## Implementation Tasks

### 1. Preparation & Branching
```bash
make start-issue ID=X NAME=short-name
```

### 2. [Task Name]
- **File**: `src/<pkg>/<module>.py`
- **Change**: [What to add/modify, concretely]

### 3..N. [One task per block, same File / Change format]

### N+1. Verification & Quality Gates
```bash
make test-issue ID=X
make check
```

### N+2. Git & Issue Finish
```bash
make finish-issue ID=X MSG="feat(scope): description"
```

### N+3. Milestone Finish (ONLY if this issue closes the milestone)
```bash
make finish-milestone MILESTONE=MX
```

## Decisions
- [Only if autonomous design decisions were made: decision + one-line rationale]
````

- Tasks 2..N are atomic: one task = one block = one file (or a small cohesive group of files).
- N+1, N+2 and N+3 are written with their real numbers (e.g. tasks 2-5 → Verification = 6,
  Git = 7, Milestone = 8).
- `## Decisions` only appears when autonomous decisions were made.

## 6. Makefile and pyproject conventions
- The `Makefile` is complete and self-documented: `help` is the default target and every target
  has a `## description`.
- Lifecycle targets validate their parameters and abort with a clear message:
  `start-issue ID NAME [TYPE]`, `finish-issue ID MSG`, `finish-milestone MILESTONE`.
- Quality targets: `venv`, `deps`, `lint`, `format`, `typecheck`, `check`, `test`, `test-unit`,
  `test-integration`, `test-issue ID`, `ci`, `clean`, `security`.
- `pyproject.toml` holds the optional-dependency groups (`dev`, one per layer, `all`) and the
  ruff, mypy (strict) and pytest configuration.
- pytest runs with `--strict-markers`: every new test carries `@pytest.mark.issue_X`, and the
  `issue_X` marker is registered in `pyproject.toml` **in the same issue**.
- `make test-issue ID=X` fails on purpose when no test is marked `issue_X`.

## 7. Language
- Code, identifiers, docstrings, commit messages and documentation (README, `docs/`, issues,
  milestones, `.agents/`) are written in **English only**.
- Chat replies to the user may be in Spanish.

## 8. Autonomy and design decisions
- Technical doubts or open questions do not block the work: the agent takes the most robust
  decision aligned with the architecture, records it in `## Decisions` (decision + one-line
  rationale) and moves on.
- Autonomy covers technical decisions only. It never justifies ignoring or postponing a user
  question.

## 9. Who executes what
- **User only**: anything that changes git/GitHub state: `make start-issue`, `make finish-issue`,
  `make finish-milestone`, the initial git commands, `scripts/bootstrap_github.sh`, and any
  `git commit/push/checkout/merge` or state-changing `gh ...` command.
- **Agent**: read-only git (`git status`, `git diff`, `git log`) and all verification commands:
  `make venv`, `make deps`, `make format`, `make lint`, `make typecheck`, `make check`,
  `make test-issue ID=X`, `make test`, `make ci`, `make security`.
- Commands that need network (e.g. `make deps` after adding a dependency, `make security`):
  the agent asks for explicit permission (or asks the user to run them) instead of retrying.

## 10. Quality gate
- No code is handed over unless ruff (lint + format), mypy (strict) and the issue tests pass.
  Minimum: `make check` and `make test-issue ID=X`, both green.
- Failures are fixed by the agent before reporting.
- Disabling ruff/mypy rules or using `# noqa` / `# type: ignore` to pass the gate is forbidden
  unless justified in `## Decisions`.

## 11. Communication
- Ultra-short replies: what was done, whether checks passed, and the next command to run.
- Phase A report:
  ```
  ✅ Plan: docs/issue_X_name.md (N tasks)
  ▶️ Next command: make start-issue ID=X NAME=short-name
  ```
- Phase B report:
  ```
  ✅ Done: [what was done, 1 to 3 lines]
  🧪 Checks: ruff ✅ · mypy ✅ · tests issue_X ✅ (N passed)
  ▶️ Next command: make finish-issue ID=X MSG="type(scope): description"
  🏁 [Only if it closes a milestone] Then: make finish-milestone MILESTONE=MX
  ```
- User questions are answered FIRST; no more code is written until the user says so.
- When blocked (hanging command, repeated error, missing permissions or network), the agent
  reports it in ONE line with what it needs, instead of retrying silently.

## 12. Internal plans
- The ONLY source of truth is `docs/issue_X_name.md`; a plan exists only when that file exists
  in the repo.
- Internal checklists, task lists or artifacts are temporary helpers only. If they differ from
  the issue file, the file wins, and any scope change is reflected there first.

## 13. Project invariants (P-10)
- **Paper trading only**: no real broker, no real money. `TRADING_MODE` accepts only `paper`.
- Risk limits are deterministic and enforced outside the LLM; the agent cannot bypass them.
- Every decision is persisted with its full trace (thoughts, tool calls, observations, tokens,
  cost).
- Every external integration sits behind an interface with a fake for tests.
