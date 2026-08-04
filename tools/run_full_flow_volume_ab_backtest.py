"""Run a cached historical PA full-workflow A/B experiment from the command line.

The command is intentionally opt-in because every candidate can make three
model calls (fast screen, Stage 1, Stage 2).  It uses the project data cache,
keeps research records out of the production pending-record directory, disables
historical setup statistics and experience retrieval to avoid future leakage,
and caches each LLM result for repeatable reruns.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pa_agent.ai.client_factory import create_ai_client
from pa_agent.ai.json_validator import JsonValidator
from pa_agent.ai.prompt_assembler import PromptAssembler
from pa_agent.ai.router import route_strategy_files
from pa_agent.backtest.full_flow import (
    CompactLLMScreener,
    FullFlowABBacktester,
    FullFlowConfig,
    JsonReplayCache,
    OrchestratorPipelineAdapter,
)
from pa_agent.config.paths import PROMPT_DIR, SETTINGS_JSON_PATH
from pa_agent.config.settings import load_settings
from pa_agent.data.kline_cache import KlineCacheStore
from pa_agent.orchestrator.two_stage import TwoStageOrchestrator
from pa_agent.records.pending_writer import PendingWriter


class _EmptyExperienceReader:
    """Prevent records created after an as-of date from entering its prompts."""

    def read_top5(self, _cycle_position: str) -> list[object]:
        return []

    def read_for_stage2(self, _cycle_position: str, **_kwargs: object) -> list[object]:
        return []


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="K-line cache source, e.g. yfinance")
    parser.add_argument("--symbol", required=True, help="Cached symbol, e.g. 600519.SS")
    parser.add_argument("--timeframe", default="1d", help="Cached timeframe, default: 1d")
    parser.add_argument("--window", type=int, default=100, help="Closed bars per model snapshot")
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=40,
        help="Shared price-only candidate cap; controls LLM cost",
    )
    parser.add_argument(
        "--max-holding-bars",
        type=int,
        default=30,
        help="Research-only simulator holding cap; use 0 for no cap",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("cache") / "full_flow_llm",
        help="LLM replay cache; safe to reuse only with the same model/prompt revision",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports") / "full_flow_volume_ab.json",
        help="JSON summary output path",
    )
    parser.add_argument(
        "--research-records",
        type=Path,
        default=Path("cache") / "research_full_flow_ab_records",
        help="Separate record directory for this experiment; never use production pending records",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    cache_entry = KlineCacheStore().read(args.source, args.symbol, args.timeframe)
    if cache_entry is None or not cache_entry.bars:
        raise SystemExit(
            f"No cached K-lines for source={args.source}, symbol={args.symbol}, timeframe={args.timeframe}."
        )

    settings = load_settings(SETTINGS_JSON_PATH)
    client = create_ai_client(settings.provider)
    empty_experience = _EmptyExperienceReader()
    orchestrator = TwoStageOrchestrator(
        client=client,
        assembler=PromptAssembler(
            prompt_dir=PROMPT_DIR,
            experience_reader=empty_experience,
            prompt_settings=settings.prompt,
        ),
        router=route_strategy_files,
        validator=JsonValidator(settings),
        pending_writer=PendingWriter(
            pending_dir=args.research_records,
            api_key=settings.provider.api_key,
        ),
        exp_reader=empty_experience,
        settings=settings,
        # A non-ledger sentinel avoids loading setup results created after the
        # historical as-of date, which would be a look-ahead leak.
        setup_stats_ledger=object(),
    )
    config = FullFlowConfig(
        window_bars=max(20, args.window),
        max_logic_candidates=max(1, args.max_candidates),
        max_holding_bars=None if args.max_holding_bars <= 0 else args.max_holding_bars,
        model_revision=settings.provider.model,
    )
    runner = FullFlowABBacktester(
        fast_screener=CompactLLMScreener(client),
        pipeline=OrchestratorPipelineAdapter(orchestrator),
        config=config,
        cache=JsonReplayCache(args.cache_dir),
    )
    comparison = runner.run(
        symbol=args.symbol,
        timeframe=args.timeframe,
        bars=cache_entry.bars,
    )
    payload = comparison.to_payload()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nSaved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
