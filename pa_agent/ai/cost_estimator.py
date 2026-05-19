"""Cost estimation for DeepSeek API calls."""
from __future__ import annotations

from pa_agent.ai.deepseek_client import AIUsage
from pa_agent.config.settings import PricingTable


def estimate_cost(usage: AIUsage, pricing: PricingTable) -> float:
    """Compute the CNY cost for a single API call.

    Formula:
        cost = (cached_hit * input_cache_hit
                + (prompt - cached_hit) * input_cache_miss
                + completion * output) / 1_000_000

    Returns cost in CNY (yuan).
    """
    hit = usage.cached_prompt_tokens
    miss = max(0, usage.prompt_tokens - hit)
    out = usage.completion_tokens

    return (
        hit * pricing.input_cache_hit
        + miss * pricing.input_cache_miss
        + out * pricing.output
    ) / 1_000_000


def breakdown(usage: AIUsage, pricing: PricingTable) -> dict[str, float]:
    """Return a three-item cost breakdown dict for UI display.

    Keys: 'cache_hit_cny', 'cache_miss_cny', 'output_cny', 'total_cny'
    """
    hit = usage.cached_prompt_tokens
    miss = max(0, usage.prompt_tokens - hit)
    out = usage.completion_tokens

    cache_hit_cny = hit * pricing.input_cache_hit / 1_000_000
    cache_miss_cny = miss * pricing.input_cache_miss / 1_000_000
    output_cny = out * pricing.output / 1_000_000

    return {
        "cache_hit_cny": cache_hit_cny,
        "cache_miss_cny": cache_miss_cny,
        "output_cny": output_cny,
        "total_cny": cache_hit_cny + cache_miss_cny + output_cny,
    }
