"""Export the OKX top-five portfolio backtest to JSON and CSV files."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from pa_agent.config.paths import PROJECT_ROOT
from pa_agent.crypto.backtest import CryptoBacktestConfig, run_okx_crypto_backtest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--target-volatility", type=float, default=0.15)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--rebalance-days", type=int, default=7)
    parser.add_argument("--strategy-version", choices=("1.0", "2.0"), default="2.0")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "reports" / "crypto",
    )
    return parser


def _write_summary(path: Path, result: dict) -> None:
    sections = {
        "strategy": result["metrics"],
        "btc_benchmark": result["benchmark"],
        "early_70_pct": result["validation"]["early_70_pct"],
        "recent_30_pct": result["validation"]["recent_30_pct"],
        "double_friction": result["stress"],
    }
    if result.get("baseline_v1"):
        sections["baseline_v1"] = result["baseline_v1"]["metrics"]
    fieldnames = [
        "section",
        "total_return",
        "cagr",
        "annual_volatility",
        "sharpe",
        "max_drawdown",
        "calmar",
        "positive_days_pct",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for section, metrics in sections.items():
            writer.writerow(
                {
                    "section": section,
                    **{key: metrics.get(key) for key in fieldnames if key != "section"},
                }
            )


def _write_curve(path: Path, result: dict) -> None:
    fieldnames = ["date", "equity", "benchmark", "drawdown", "gross_exposure"]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(result["curve"])


def main() -> int:
    args = _parser().parse_args()
    config = CryptoBacktestConfig(
        years=args.years,
        target_volatility=args.target_volatility,
        cost_bps=args.cost_bps,
        rebalance_days=args.rebalance_days,
        strategy_version=args.strategy_version,
    )
    result = run_okx_crypto_backtest(config)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    version = str(result["strategy"]["version"]).replace(".", "_")
    stem = f"okx_top5_v{version}_backtest_{stamp}"
    json_path = output_dir / f"{stem}.json"
    curve_path = output_dir / f"{stem}_daily.csv"
    summary_path = output_dir / f"{stem}_summary.csv"

    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_curve(curve_path, result)
    _write_summary(summary_path, result)
    print(
        json.dumps(
            {
                "json": str(json_path),
                "daily_csv": str(curve_path),
                "summary_csv": str(summary_path),
                "sample": result["sample"],
                "metrics": result["metrics"],
                "benchmark": result["benchmark"],
                "validation": result["validation"],
                "stress": result["stress"],
                "annual_returns": result["annual_returns"],
                "latest": result["latest"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
