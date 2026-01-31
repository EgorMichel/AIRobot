"""Manual mode stub."""
from __future__ import annotations
from core.types import Event, ModeContext
from modes.base import IControlMode


class ManualMode(IControlMode):
    def enter(self, ctx: ModeContext) -> None:
        pass

    def handle_event(self, event: Event) -> None:
        pass

    def tick(self) -> None:
        pass

    def exit(self) -> None:
        pass
