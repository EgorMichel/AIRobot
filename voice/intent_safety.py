"""Intent safety stub."""
from __future__ import annotations
from typing import Protocol
from core.types import Intent, Result, RobotState


class IIntentSafety(Protocol):
    def validate(self, intent: Intent, state: RobotState) -> Result[None]: ...
