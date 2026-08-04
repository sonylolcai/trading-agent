"""Run a compact V2 parameter plateau search on one shared OKX dataset."""
from __future__ import annotations

import csv
import itertools
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from pa_agent.config.paths import PROJECT_ROOT
from pa_agent.crypto.backtest import (
    CryptoBacktestConfig,
    backtest_crypto_prices,
    fetch_okx_crypto_closes,
)


def main() -> int:
    base = CryptoBacktestConfig(
        years=5,
        target_volatility=0.15,
        cost_bps=10,
        strategy_version="2.0",
    )
    closes, source, requested_start = fetch_okx_crypto_closes(base)
    baseline = backtest_crypto_prices(
        closes,
        replace(base, strategy_version="1.0"),
        requested_start=requested_start,
        include_baseline=False,
    )
    rows = []
    combinations = itertools.product(
        (0.00, 0.05, 0.10),
        (0.20, 0.28),
        (2.0, 2.5, 3.0),
        (3, 7),
    )
    for entry_momentum, range_efficiency, trailing_sigma, cooldown_days in combinations:
        config = replace(
            base,
            entry_momentum=entry_momentum,
            range_efficiency=range_efficiency,
            trailing_sigma=trailing_sigma,
            cooldown_days=cooldown_days,
        )
        result = backtest_crypto_prices(
            closes,
            config,
            requested_start=requested_start,
            include_baseline=False,
        )
        rows.append(
            {
                "entry_momentum": entry_momentum,
                "range_efficiency": range_efficiency,
                "trailing_sigma": trailing_sigma,
                "cooldown_days": cooldown_days,
                "cagr": result["metrics"]["cagr"],
                "max_drawdown": result["metrics"]["max_drawdown"],
                "sharpe": result["metrics"]["sharpe"],
                "recent_cagr": result["validation"]["recent_30_pct"]["cagr"],
                "recent_max_drawdown": result["validation"]["recent_30_pct"][
                    "max_drawdown"
                ],
                "stress_cagr": result["stress"]["cagr"],
                "annual_turnover": result["metrics"]["annual_turnover"],
                "emergency_exits": result["diagnostics"]["emergency_exit_count"],
                "range_days": result["regime_days"].get("range", 0),
            }
        )

    rows.sort(
        key=lambda row: (
            row["recent_cagr"] > 0,
            row["stress_cagr"],
            row["sharpe"],
        ),
        reverse=True,
    )
    output_dir = PROJECT_ROOT / "reports" / "crypto"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    csv_path = output_dir / f"okx_top5_v2_sensitivity_{stamp}.csv"
    json_path = output_dir / f"okx_top5_v2_sensitivity_{stamp}.json"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        "source": source,
        "baseline_v1": baseline["metrics"],
        "tested_combinations": len(rows),
        "top_10": rows[:10],
        "all_results": rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"csv": str(csv_path), "json": str(json_path), **payload}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
