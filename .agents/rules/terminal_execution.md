---
description: Constraints for terminal execution
---
# Rule: Do not execute terminal commands (with exceptions)

The user has specified that they prefer to execute state-changing or repository-altering commands themselves, but there are exceptions for verification.

**Prohibitions:**
- DO NOT execute Git commands (e.g., `git commit`, `git push`, `git reset`) or git-altering `make` tasks (e.g. `make start-issue`, `make finish-issue`). Let the user do these.

**Allowed Commands:**
- You MAY execute read-only commands for searching files (`grep`, `ls`, `find`), reading code or logs (`cat`, `gh issue view`), provided the built-in tools (`view_file`, `list_dir`, `grep_search`) are insufficient.
- You MAY execute verification and quality-gate commands (e.g., `make check`, `make test`, `make format`, `pytest`, `mypy`, `ruff`) when they are part of the development cycle for the tasks you have been assigned to implement. This is to ensure the code you produce is correct and type-safe before presenting it to the user.
