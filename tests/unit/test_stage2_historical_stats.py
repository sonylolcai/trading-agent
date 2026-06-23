from __future__ import annotations

import copy
import json

from pa_agent.ai.json_validator import Ok
from pa_agent.ai.stage2_normalizer import normalize_stage2
from tests.fixtures.ai_payloads import VALID_STAGE2_ORDER
from tests.fixtures.validators import schema_test_validator


def test_stage2_schema_accepts_historical_win_rate_fields() -> None:
    payload = copy.deepcopy(VALID_STAGE2_ORDER)
    payload["decision"].update(
        {
            "estimated_win_rate_basis": "historical",
            "historical_win_rate_for_this_setup": "52.3",
            "historical_sample_count": "47",
            "historical_expectancy_r": "0.18",
        }
    )

    out = normalize_stage2(payload)

    decision = out["decision"]
    assert decision["estimated_win_rate_basis"] == "historical"
    assert decision["historical_win_rate_for_this_setup"] == 52.3
    assert decision["historical_sample_count"] == 47
    assert decision["historical_expectancy_r"] == 0.18

    result = schema_test_validator().validate(
        "stage2",
        json.dumps(out, ensure_ascii=False),
    )
    assert isinstance(result, Ok)
