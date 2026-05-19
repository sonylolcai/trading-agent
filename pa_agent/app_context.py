"""Application context wiring shared resources without global singletons."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AppContext:
    """Carries shared resources to GUI widgets and orchestrators.

    Fields are typed as ``Any`` so that early tasks can bootstrap a window
    without pulling in modules that don't exist yet.  Later tasks replace
    the placeholders with real typed objects.
    """

    settings: Any = None
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("pa_agent"))
    event_bus: Any = None

    # Data layer
    data_source: Any = None       # DataSource implementation
    buffer: Any = None            # KlineBuffer

    # AI / orchestration layer
    client: Any = None            # DeepSeekClient
    assembler: Any = None         # PromptAssembler
    router: Any = None            # route_strategy_files callable or StrategyRouter
    validator: Any = None         # JsonValidator
    exc_counter: Any = None       # ExceptionCounter
    pending_writer: Any = None    # PendingWriter
    exp_reader: Any = None        # ExperienceReader
    ledger: Any = None            # SessionTokenLedger

    @classmethod
    def bootstrap(cls) -> "AppContext":
        # Real wiring happens in later tasks (config, security, event bus).
        # For now we just hand back a context with a default logger so that
        # main.py can show a window during the skeleton smoke test.
        return cls()
