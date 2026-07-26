# AGENTS.md

> Scaffolded by [repo-harness](https://github.com/Yogeshwar-CM/repo-harness).  
> This is a **README for coding agents** ([agents.md](https://agents.md/) format). Keep it short, specific, and current.

## What this repo is

**context-tax** — _(one sentence: what problem it solves)_

## Stack

- Detected: **python**
- Layout signals: `.py`×4, `.md`×2, `.toml`×1, `.yml`×1
- Packages / workspace dirs: n/a (single package)
- Entry points: `src`
- Tests: `tests`

## Setup & run

```bash
pip install -e .
pytest
```

## Commands

| Task | Command |
|------|---------|
| Install | `pip install -e .` |
| Test | `pytest` |
| cli:context-tax | `context-tax` |

## Architecture map (keep this updated)

Agents should navigate by this TOC — not by dumping the whole tree into context.

| Area | Path | Notes |
|------|------|-------|
| Core logic | | |
| API / CLI surface | | |
| UI | | |
| Data / persistence | | |
| Tests | `tests` | |
| CI | `.github/workflows/` | |

## Hard rules

1. Read this file and only the paths you will touch before editing.
2. Prefer small, reviewable diffs. No drive-by refactors.
3. Never invent secrets, tokens, or production URLs. Never commit `.env`.
4. Match existing style; do not reformat unrelated files.
5. Run the relevant test/lint commands for code you change.
6. If requirements are ambiguous, state assumptions in the PR/commit body.

## Do not touch (unless explicitly asked)

- Lockfile-only churn without a dependency change
- Generated folders (`dist/`, `build/`, `.next/`, etc.)
- Unrelated dependency major upgrades
- Mass renames / moves mixed into feature work

## PR / commit expectations

- Title explains *why*, not only *what*
- Tests updated when behavior changes
- No secrets in the diff
- Update this file if architecture or commands changed

## Definition of done

- [ ] Change is scoped to the request
- [ ] Tests / typecheck / lint for touched areas pass
- [ ] Docs (`AGENTS.md` / README) updated if needed
- [ ] No credential material

---
_Tip: nested `AGENTS.md` files in subpackages override/amplify root guidance for that subtree._
