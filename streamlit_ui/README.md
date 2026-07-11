# Dashboard

Bare-bones Streamlit skeleton for factor-stat-arb. Runs on port **8502**
(isolated from trading-system's default 8501).

```bash
uv run main.py up streamlit          # start via the project entry point
# or
uv run streamlit run streamlit_ui/streamlit_app.py
```

`streamlit_app.py` is a single tabbed app:

- **Overview** - live universe/data status from the database (wired)
- **Factor Structure** / **Signals** / **Backtest** - placeholders for the
  milestones in [`docs/PROJECT_SPEC.md`](../docs/PROJECT_SPEC.md)

Grow the Factor Lab here as those milestones land.
