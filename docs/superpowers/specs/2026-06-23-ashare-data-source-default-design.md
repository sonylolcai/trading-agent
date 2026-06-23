# A-Share Data Source Default Design

## Problem

The app currently defaults to MT5 and the GUI exposes only MT5 and TradingView. This blocks A-share users when the local MT5 terminal is missing, producing errors such as `MetaTrader 5 x64 not found`.

## Decision

Expose existing A-share data sources in the GUI and make the built-in East Money source the default. MT5 remains available for users who explicitly need gold/forex through a local MT5 terminal, but it should not be the first path for A-share work.

## Scope

- Show these GUI data-source choices: East Money(A-share), AkShare(A-share), Tushare(A-share/token), TradingView, MT5.
- Change default `GeneralSettings.last_data_source` from `mt5` to `eastmoney`.
- Change default startup symbol/timeframe to the existing A-share defaults.
- Keep `normalize_data_source_kind()` accepting MT5/TradingView/A-share kinds.
- Keep MT5 behavior unchanged when the user explicitly selects it.
- Update tests that previously expected A-share sources to be hidden.

## Non-Goals

- Do not remove MT5.
- Do not install external packages.
- Do not change A-share HTTP fetching internals.
- Do not redesign the whole settings dialog.

## User-Facing Result

New installs and missing-config cases open on East Money with an A-share symbol. The GUI dropdown allows switching among A-share sources without editing `settings.json`. MT5 errors only appear if the user actively chooses MT5 and their terminal is unavailable.
