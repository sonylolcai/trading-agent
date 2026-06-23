"""ExperienceReader — read-only access to the experience library.

Scans ``success_cases/`` and ``failure_cases/`` subdirectories under
``EXPERIENCE_DIR / cycle_position /``, sorts files by the timestamp
embedded in their filenames (descending, newest first), and returns
the top 5 entries across both directories combined.

File naming convention (timestamp portion):
    YYYY-MM-DD_HH-mm-ss   (minutes use '-', not ':')

Example filename:
    2026-05-18_14-30-45_XAUUSD_1h.json

This module is strictly read-only — it never writes or deletes files.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pa_agent.records.schema import ExperienceEntry

# Regex to extract the timestamp portion from a filename.
_TS_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})")
_TS_FORMAT = "%Y-%m-%d_%H-%M-%S"


def _default_logger() -> logging.Logger:
    return logging.getLogger(__name__)


def _parse_timestamp_ms(filename: str) -> Optional[int]:
    """Extract and parse the timestamp from a filename.

    Returns the timestamp in milliseconds, or ``None`` if the filename
    does not contain a parseable timestamp.
    """
    match = _TS_PATTERN.search(filename)
    if not match:
        return None
    ts_str = match.group(1)
    try:
        dt = datetime.strptime(ts_str, _TS_FORMAT)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None


def _norm_text(value: object) -> str:
    return str(value or "").strip().lower()


def _extract_outcome(content: dict[str, Any]) -> dict[str, Any]:
    """Return normalized outcome metadata from an experience JSON blob."""
    outcome = content.get("outcome")
    if outcome is None:
        outcome = content.get("result")
    if outcome is None:
        outcome = content.get("trade_result")
    label = ""
    r_multiple: float | None = None
    exit_reason = ""

    if isinstance(outcome, dict):
        label = str(
            outcome.get("label")
            or outcome.get("status")
            or outcome.get("result")
            or outcome.get("outcome")
            or ""
        ).strip()
        exit_reason = str(outcome.get("exit_reason") or outcome.get("reason") or "").strip()
        r_source = (
            outcome.get("r_multiple")
            if outcome.get("r_multiple") is not None
            else outcome.get("profit_r")
        )
    else:
        label = str(outcome or "").strip()
        r_source = None

    if r_source is None:
        for key in ("r_multiple", "profit_r", "pnl_r", "profit_ratio"):
            if content.get(key) is not None:
                r_source = content.get(key)
                break

    try:
        if r_source is not None:
            r_multiple = float(r_source)
    except (TypeError, ValueError):
        r_multiple = None

    label_norm = _norm_text(label)
    has_outcome = bool(label_norm or exit_reason or r_multiple is not None)
    if r_multiple is not None:
        kind = "winner" if r_multiple > 0 else "loser" if r_multiple < 0 else "flat"
    elif label_norm in {"win", "winner", "success", "profit", "tp", "take_profit"}:
        kind = "winner"
    elif label_norm in {"loss", "loser", "failure", "stop", "sl", "stop_loss"}:
        kind = "loser"
    else:
        kind = "unknown"

    return {
        "has_outcome": has_outcome,
        "kind": kind,
        "label": label,
        "r_multiple": r_multiple,
        "exit_reason": exit_reason,
    }


class ExperienceReader:
    """Read experience entries from the experience library (read-only).

    Parameters
    ----------
    experience_dir:
        Root directory of the experience library.  Defaults to
        ``pa_agent.config.paths.EXPERIENCE_DIR`` when ``None``.
    logger:
        Optional logger instance.  A module-level logger is used when
        ``None``.
    """

    def __init__(
        self,
        experience_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if experience_dir is None:
            from pa_agent.config.paths import EXPERIENCE_DIR
            experience_dir = EXPERIENCE_DIR

        self._experience_dir = experience_dir
        self._logger = logger or _default_logger()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_top5(self, cycle_position: str) -> list[ExperienceEntry]:
        """Return the 5 most-recent experience entries for *cycle_position*.

        Scans both ``success_cases/`` and ``failure_cases/`` subdirectories
        under ``EXPERIENCE_DIR / cycle_position /``.  Files are sorted by
        the timestamp embedded in their filenames (descending).  The top 5
        entries across both directories combined are returned.

        Parameters
        ----------
        cycle_position:
            The cycle position label (e.g. ``"micro_channel"``).

        Returns
        -------
        list[ExperienceEntry]
            Up to 5 entries, newest first.  Returns an empty list when no
            readable entries are found.
        """
        entries = self._read_all(cycle_position)
        entries.sort(key=lambda e: e.timestamp_ms, reverse=True)
        return entries[:5]

    def read_for_stage2(
        self,
        cycle_position: str,
        *,
        direction: str = "",
        patterns: list[str] | None = None,
        max_entries: int = 3,
        max_chars_per_entry: int = 400,
        setup_key: str | None = None,
        require_outcome: bool = True,
        include_winners: bool = True,
        include_losers: bool = True,
    ) -> list[ExperienceEntry]:
        """Return recent experience entries filtered for Stage 2 relevance."""
        del max_chars_per_entry  # PromptAssembler owns text truncation.
        entries = self._read_all(cycle_position)
        if not entries:
            return []

        dir_norm = _norm_text(direction)
        pattern_set = {
            _norm_text(p) for p in (patterns or []) if str(p).strip()
        }
        setup_norm = _norm_text(setup_key)
        ranked: list[tuple[int, ExperienceEntry, dict[str, Any]]] = []

        for entry in entries:
            content = entry.content if isinstance(entry.content, dict) else {}
            outcome = _extract_outcome(content)
            if require_outcome and not outcome["has_outcome"]:
                continue
            if outcome["kind"] == "winner" and not include_winners:
                continue
            if outcome["kind"] == "loser" and not include_losers:
                continue
            if outcome["kind"] == "unknown" and require_outcome:
                continue

            score = 0
            ent_setup = _norm_text(content.get("setup_key") or content.get("setup"))
            if setup_norm and ent_setup == setup_norm:
                score += 8
            ent_dir = _norm_text(content.get("direction"))
            if dir_norm and ent_dir == dir_norm:
                score += 3
            ent_patterns = content.get("detected_patterns") or []
            if not ent_patterns:
                ent_patterns = content.get("patterns") or []
            if pattern_set and isinstance(ent_patterns, list):
                overlap = pattern_set.intersection(
                    {_norm_text(p) for p in ent_patterns}
                )
                score += len(overlap)
            if outcome["has_outcome"]:
                score += 1
            ranked.append((score, entry, outcome))

        ranked.sort(key=lambda item: (item[0], item[1].timestamp_ms), reverse=True)
        cap = max(0, min(max_entries, 10))
        if cap == 0:
            return []

        if include_winners and include_losers:
            winners = [item for item in ranked if item[2]["kind"] == "winner"]
            losers = [item for item in ranked if item[2]["kind"] == "loser"]
            balanced: list[ExperienceEntry] = []
            wi = li = 0
            while len(balanced) < cap and (wi < len(winners) or li < len(losers)):
                if wi < len(winners):
                    balanced.append(winners[wi][1])
                    wi += 1
                    if len(balanced) >= cap:
                        break
                if li < len(losers):
                    balanced.append(losers[li][1])
                    li += 1
            if len(balanced) < cap:
                used = {entry.filename for entry in balanced}
                balanced.extend(
                    entry for _, entry, _ in ranked if entry.filename not in used
                )
            return balanced[:cap]

        return [entry for _, entry, _ in ranked[:cap]]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_all(self, cycle_position: str) -> list[ExperienceEntry]:
        base_dir = self._experience_dir / cycle_position
        candidates: list[tuple[int, str, Path]] = []

        for case_type, subdir_name in (("success", "success_cases"), ("failure", "failure_cases")):
            subdir = base_dir / subdir_name
            if not subdir.exists():
                self._logger.debug(
                    "ExperienceReader: directory does not exist, skipping: %s", subdir
                )
                continue

            for file_path in subdir.iterdir():
                if not file_path.is_file() or file_path.suffix.lower() != ".json":
                    continue
                ts_ms = _parse_timestamp_ms(file_path.name)
                if ts_ms is None:
                    self._logger.warning(
                        "ExperienceReader: cannot parse timestamp from filename, skipping: %s",
                        file_path.name,
                    )
                    continue
                candidates.append((ts_ms, case_type, file_path))

        entries: list[ExperienceEntry] = []
        for ts_ms, case_type, file_path in candidates:
            content = self._read_json(file_path)
            if content is None:
                continue
            entries.append(
                ExperienceEntry(
                    filename=file_path.name,
                    case_type=case_type,
                    cycle_position=cycle_position,
                    timestamp_ms=ts_ms,
                    content=content,
                )
            )
        return entries

    def _read_json(self, path: Path) -> Optional[dict]:
        """Read and parse a JSON file.

        Returns the parsed dict, or ``None`` on any error (with a warning
        logged).
        """
        try:
            text = path.read_text(encoding="utf-8")
            return json.loads(text)
        except OSError as exc:
            self._logger.warning(
                "ExperienceReader: cannot read file %s: %s", path, exc
            )
            return None
        except json.JSONDecodeError as exc:
            self._logger.warning(
                "ExperienceReader: invalid JSON in file %s: %s", path, exc
            )
            return None
