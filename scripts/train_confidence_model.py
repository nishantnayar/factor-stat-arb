"""Train the factor-basket confidence model and persist it to disk.

Bootstraps training data from strategy_engine.basket_backtest_run.trade_log
(simulated backtest trades) joined with strategy_engine.basket_registry
features, since no live paper trades exist yet (milestone 7 will produce
those; swap the training source later without changing the model interface).

Usage:
    uv run scripts/train_confidence_model.py
    uv run scripts/train_confidence_model.py --out models/confidence_model.joblib
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import joblib  # noqa: E402

from src.services.strategy_engine.factor_stat_arb.confidence_model import (  # noqa: E402
    ConfidenceModel,
    build_training_frame,
)

DEFAULT_OUT = ROOT / "models" / "confidence_model.joblib"


def main() -> int:
    p = argparse.ArgumentParser(description="Train the factor-basket confidence model")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output path")
    args = p.parse_args()

    print("Building training frame from basket_backtest_run.trade_log...")
    frame = build_training_frame()
    if frame.empty:
        print(
            "No labeled trades found. Run scripts/backtest_factor_baskets.py "
            "against discovered baskets first to generate trade_log data."
        )
        return 1

    print(f"Training on {len(frame)} simulated trades...")
    try:
        model = ConfidenceModel().fit(frame)
    except ValueError as exc:
        print(f"Training failed: {exc}")
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.out)
    print(f"Saved confidence model to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
