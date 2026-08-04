from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pa_agent.config.environment import load_project_env
from pa_agent.crypto.okx import OkxClient, read_okx_connection_status


def _response(data: list[object]) -> bytes:
    return json.dumps({"code": "0", "msg": "", "data": data}).encode()


def test_public_time_does_not_send_private_headers() -> None:
    captured = []

    def transport(request, _timeout):
        captured.append(request)
        return 200, _response([{"ts": "1720000000000"}])

    client = OkxClient(
        api_key="",
        api_secret="",
        passphrase="",
        transport=transport,
        throttle=lambda _: None,
    )

    assert client.server_time_ms() == 1_720_000_000_000
    assert captured[0].get_header("Ok-access-key") is None


def test_demo_balance_is_signed_and_uses_simulation_header() -> None:
    captured = []

    def transport(request, _timeout):
        captured.append(request)
        return 200, _response(
            [
                {
                    "totalEq": "1234.5",
                    "details": [
                        {"ccy": "USDT", "eq": "1200", "availBal": "1100"},
                        {"ccy": "BTC", "eq": "0", "availBal": "0"},
                    ],
                }
            ]
        )

    client = OkxClient(
        api_key="demo-key",
        api_secret="demo-secret",
        passphrase="demo-pass",
        demo_trading=True,
        transport=transport,
    )

    account = client.account_balance()

    assert account["total_equity_usd"] == 1234.5
    assert account["currencies"] == [
        {"currency": "USDT", "equity": 1200.0, "available": 1100.0}
    ]
    request = captured[0]
    assert request.get_header("Ok-access-key") == "demo-key"
    assert request.get_header("X-simulated-trading") == "1"
    assert request.get_header("Ok-access-sign")


def test_history_candles_paginates_deduplicates_and_keeps_closed_rows() -> None:
    pages = {
        None: [
            ["3000", "3", "4", "2", "3.5", "30", "0", "0", "1"],
            ["2000", "2", "3", "1", "2.5", "20", "0", "0", "1"],
            ["1500", "1", "2", "0", "1.5", "10", "0", "0", "0"],
        ],
        "2000": [
            ["2000", "2", "3", "1", "2.5", "20", "0", "0", "1"],
            ["1000", "1", "2", "0", "1.5", "10", "0", "0", "1"],
        ],
    }

    def transport(request, _timeout):
        after = parse_qs(urlparse(request.full_url).query).get("after", [None])[0]
        return 200, _response(pages[after])

    client = OkxClient(transport=transport, throttle=lambda _: None)
    candles = client.history_candles("BTC-USDT", start_ms=1000)

    assert [item.ts_ms for item in candles] == [1000, 2000, 3000]
    assert candles[-1].close == 3.5


def test_safe_status_skips_private_endpoint_without_credentials() -> None:
    calls = []

    def transport(request, _timeout):
        calls.append(request.full_url)
        return 200, _response([{"ts": "1720000000000"}])

    status = read_okx_connection_status(
        OkxClient(
            api_key="",
            api_secret="",
            passphrase="",
            transport=transport,
        )
    )

    assert status["public_api_reachable"] is True
    assert status["credentials_configured"] is False
    assert status["authenticated"] is False
    assert calls == ["https://www.okx.com/api/v5/public/time"]


def test_project_env_loads_values_without_overriding_process(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OKX_API_KEY=file-key\nOKX_API_SECRET=file-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OKX_API_KEY", "process-key")
    monkeypatch.delenv("OKX_API_SECRET", raising=False)

    assert load_project_env(env_path) is True

    assert OkxClient().api_key == "process-key"
    assert OkxClient().api_secret == "file-secret"
