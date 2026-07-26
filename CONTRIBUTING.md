# Contributing

## Dev setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## Guidelines

- Keep the CLI **stdlib-only** (no required deps) unless there is a strong reason.
- Token estimates should stay fast and dependency-free; optional tiktoken can be a future extra.
- Add tests for any new categorization or CLI flag.
- Run tools on themselves before opening a PR.
