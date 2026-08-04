"""Small OKX REST client for public history and read-only demo account checks."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pa_agent.config.environment import load_project_env


class OkxApiError(RuntimeError):
    """Normalized OKX connectivity or response error."""

    def __init__(self, detail: str, *, status_code: int = 502) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class OkxCandle:
    ts_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


Transport = Callable[[Request, float], tuple[int, bytes]]


def _default_transport(request: Request, timeout: float) -> tuple[int, bytes]:
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured OKX URL
        return int(response.status), response.read()


class OkxClient:
    """Minimal deterministic client; it never places orders."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        passphrase: str | None = None,
        demo_trading: bool | None = None,
        timeout: float = 15.0,
        transport: Transport = _default_transport,
        throttle: Callable[[float], None] = time.sleep,
    ) -> None:
        load_project_env()
        self.base_url = (base_url or os.getenv("OKX_BASE_URL") or "https://www.okx.com").rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("OKX_API_KEY", "")
        self.api_secret = api_secret if api_secret is not None else os.getenv("OKX_API_SECRET", "")
        self.passphrase = passphrase if passphrase is not None else os.getenv(
            "OKX_API_PASSPHRASE", ""
        )
        demo_env = os.getenv("OKX_DEMO_TRADING", "1").strip().lower()
        self.demo_trading = (
            demo_trading if demo_trading is not None else demo_env not in {"0", "false", "no"}
        )
        self.timeout = timeout
        self._transport = transport
        self._throttle = throttle

    @property
    def credentials_configured(self) -> bool:
        return bool(self.api_key and self.api_secret and self.passphrase)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _signature(self, timestamp: str, method: str, request_path: str, body: str) -> str:
        message = f"{timestamp}{method.upper()}{request_path}{body}".encode()
        digest = hmac.new(self.api_secret.encode(), message, hashlib.sha256).digest()
        return base64.b64encode(digest).decode()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
        private: bool = False,
    ) -> list[Any]:
        query = urlencode(params or {})
        request_path = f"{path}?{query}" if query else path
        headers = {"Accept": "application/json", "User-Agent": "PA-Agent/0.1"}
        if private:
            if not self.credentials_configured:
                raise OkxApiError("OKX demo credentials are not configured", status_code=409)
            timestamp = self._timestamp()
            headers.update(
                {
                    "OK-ACCESS-KEY": self.api_key,
                    "OK-ACCESS-SIGN": self._signature(timestamp, method, request_path, ""),
                    "OK-ACCESS-PASSPHRASE": self.passphrase,
                    "OK-ACCESS-TIMESTAMP": timestamp,
                }
            )
            if self.demo_trading:
                headers["x-simulated-trading"] = "1"

        request = Request(
            f"{self.base_url}{request_path}",
            headers=headers,
            method=method.upper(),
        )
        try:
            status, raw = self._transport(request, self.timeout)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OkxApiError(f"OKX HTTP {exc.code}: {detail[:240]}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise OkxApiError(f"Unable to reach OKX: {exc}") from exc

        if status >= 400:
            raise OkxApiError(f"OKX HTTP {status}")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OkxApiError("OKX returned an invalid JSON response") from exc

        code = str(payload.get("code", ""))
        if code != "0":
            message = str(payload.get("msg") or "Unknown OKX error")
            raise OkxApiError(f"OKX API {code}: {message}")
        data = payload.get("data")
        if not isinstance(data, list):
            raise OkxApiError("OKX response is missing the data array")
        return data

    def server_time_ms(self) -> int:
        data = self._request("GET", "/api/v5/public/time")
        if not data or not isinstance(data[0], dict):
            raise OkxApiError("OKX server time response is empty")
        return int(data[0]["ts"])

    def account_balance(self) -> dict[str, Any]:
        data = self._request("GET", "/api/v5/account/balance", private=True)
        if not data or not isinstance(data[0], dict):
            raise OkxApiError("OKX account balance response is empty")
        account = data[0]
        currencies = [
            {
                "currency": str(item.get("ccy", "")),
                "equity": float(item.get("eq") or 0.0),
                "available": float(item.get("availBal") or 0.0),
            }
            for item in account.get("details", [])
            if isinstance(item, dict) and float(item.get("eq") or 0.0) != 0.0
        ]
        return {
            "total_equity_usd": float(account.get("totalEq") or 0.0),
            "currencies": currencies,
        }

    def history_candles(
        self,
        instrument_id: str,
        *,
        start_ms: int,
        bar: str = "1Dutc",
        limit: int = 300,
    ) -> list[OkxCandle]:
        """Fetch closed candles, oldest first, paginating backwards to start_ms."""
        candles: dict[int, OkxCandle] = {}
        after: int | None = None

        while True:
            params: dict[str, str | int] = {
                "instId": instrument_id,
                "bar": bar,
                "limit": max(1, min(limit, 300)),
            }
            if after is not None:
                params["after"] = after
            rows = self._request("GET", "/api/v5/market/history-candles", params=params)
            if not rows:
                break

            page_timestamps: list[int] = []
            for row in rows:
                if not isinstance(row, list) or len(row) < 9 or str(row[8]) != "1":
                    continue
                ts_ms = int(row[0])
                page_timestamps.append(ts_ms)
                candles[ts_ms] = OkxCandle(
                    ts_ms=ts_ms,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )

            if not page_timestamps:
                break
            oldest = min(page_timestamps)
            if oldest <= start_ms or oldest == after:
                break
            after = oldest
            self._throttle(0.11)

        return [candles[ts] for ts in sorted(candles) if ts >= start_ms]


def read_okx_connection_status(client: OkxClient | None = None) -> dict[str, Any]:
    """Return a safe status payload without exposing any credential."""
    active_client = client or OkxClient()
    payload: dict[str, Any] = {
        "provider": "OKX",
        "mode": "demo" if active_client.demo_trading else "live",
        "base_url": active_client.base_url,
        "credentials_configured": active_client.credentials_configured,
        "public_api_reachable": False,
        "authenticated": False,
    }
    payload["server_time_ms"] = active_client.server_time_ms()
    payload["public_api_reachable"] = True
    if active_client.credentials_configured:
        payload["account"] = active_client.account_balance()
        payload["authenticated"] = True
    return payload
