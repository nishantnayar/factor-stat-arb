# Contributing to Factor Stat Arb

Thanks for your interest. This is a personal research project, but the workflow below
keeps changes consistent and reviewable.

## Development setup

Requires [uv](https://github.com/astral-sh/uv) and a local PostgreSQL instance.

```bash
git clone https://github.com/nishantnayar/factor-stat-arb.git
cd factor-stat-arb

uv sync                              # uv provisions Python 3.11 and all deps
uv run scripts/check_env.py          # verify the environment

cp .env.example .env                 # then fill in POSTGRES_PASSWORD + Alpaca paper keys
uv run scripts/provision_db.py       # create the databases + schemas
uv run scripts/seed_data.py          # seed market/reference data
```

Do **not** use pip/conda/venv directly. `uv.lock` is committed - keep it in sync
(`uv add <pkg>` / `uv sync`).

## Before you commit

All of these must pass:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src/ --ignore-missing-imports
uv run pytest tests/unit -v
```

Auto-fix formatting and lint:

```bash
uv run ruff format . && uv run ruff check --fix .
```

## Conventions

- **ASCII-only source.** All `.py` under `src/` and `streamlit_ui/` (except
  `streamlit_ui/pages/`) must be ASCII - no smart quotes, en/em dashes, arrows, or
  emoji. Verify: `python -c "open('file.py','r',encoding='ascii').read()"`.
- **Tests.** Unit tests in `tests/unit/` must not touch the DB or network - mock with
  `unittest.mock`. Use `BacktestSignalGenerator` (stateless), not `SignalGenerator`.
- **Reuse the primitives.** The factor strategy reuses the baskets/pairs spread, signal,
  sizing, backtest, and risk code via `SimpleNamespace` shims - match that pattern rather
  than subclassing. See `docs/PROJECT_SPEC.md`.
- **Never place real orders.** Paper trading only; execution stays in the existing
  execution paths.

## Commits and branches

- Keep commits focused with a clear message (what and why).
- Branch off `main` for non-trivial work.
- Make sure the checks above pass before opening a PR.

See [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md) for the design and build plan, and
[`CLAUDE.md`](CLAUDE.md) for working conventions.
