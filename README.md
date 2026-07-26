# context-tax

**See which files will burn your coding-agent context window — before you paste the monorepo.**

[![CI](https://github.com/Yogeshwar-CM/context-tax/actions/workflows/ci.yml/badge.svg)](https://github.com/Yogeshwar-CM/context-tax/actions/workflows/ci.yml)

In 2026 everyone has a 200k–1M context window. Bills and quality still die the same way: agents swallow **lockfiles, `node_modules` bleed, source maps, and generated blobs** while the architecture map never gets written.

`context-tax` is a **local, zero-deps CLI** that walks a repo and answers:

1. How many tokens is this tree *roughly* worth?
2. Which files dominate?
3. What should be in `.agentignore`?
4. (Optional) What would a full dump cost at $X / M input tokens?

Pair it with [`repo-harness`](https://github.com/Yogeshwar-CM/repo-harness) (writes `AGENTS.md` + multi-tool harness files).

## Install

```bash
pip install context-tax
# from source
pip install -e ".[dev]"
```

Python 3.10+. **No API keys. No network.**

## Usage

```bash
cd your-project

# Human report
context-tax scan

# Top 40 + illustrative cost at $3 / MTok
context-tax scan --top 40 --price 3

# Machine-readable
context-tax scan --json > tax.json

# Suggest ignore rules
context-tax suggest-ignore
context-tax suggest-ignore --write        # append/create .agentignore
```

### Sample output

```
context-tax v0.1.0
root:    /work/my-app
scanned: 842 files  |  18.4 MB  |  ~1,102,440 tokens (est.)
cost*:   ~$3.3073 if an agent ingested everything (at $3.0/M input tokens)

By category
category      files         size      ~tokens
lockfile          2      12.1 MB       780,120
source          610       4.2 MB       240,010
docs             40     900.0 KB        55,200
...

Top 25 files by estimated tokens
   ~tokens        size  cat         path
   620,000      9.1 MB  lockfile    pnpm-lock.yaml
   ...
```

## How estimates work

- **Text**: `chars / 4` (common ballpark for mixed code/English). Good for **ranking**, not invoices.
- **Binary**: flagged separately; rough `bytes / 2` if counted.
- Default skips: `node_modules`, `.git`, `.venv`, `dist`, `build`, `target`, caches, etc.
- Honors simple names from `.agentignore` / `.gitignore` when present.

This is deliberately **not** a full tokenizer (no `tiktoken` dependency). Speed and portability > false precision.

## Why not just "bigger context"?

Research and production writeups keep showing:

- Source code dominates agent token use on SWE-style tasks.
- Minification / selective context can cut large fractions of input tokens.
- Full-repo dumps get expensive at multi-dollar-per-MTok prices and still **defocus** the model.

`context-tax` doesn't compress your code. It makes the **waste obvious** so humans and harnesses (AGENTS.md, ignores, path-scoped tools) can fix the workflow.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
context-tax scan -C .
```

## License

MIT © [Yogeshwar C M](https://github.com/Yogeshwar-CM)
