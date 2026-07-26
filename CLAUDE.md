# CLAUDE.md

Guidance for Claude Code when working in **context-tax**.

@AGENTS.md

## Quick facts

- Stack: python
- Prefer `AGENTS.md` as the source of truth for structure, commands, and hard rules.
- Primary test command: `pytest`

## Working style

1. Read `AGENTS.md` + relevant paths before editing.
2. Plan → minimal diff → verify with project commands.
3. Do not create parallel modules when an existing one should be extended.
4. No secrets in code, commits, or logs.
