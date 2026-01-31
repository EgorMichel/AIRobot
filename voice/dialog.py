"""Dialog manager stub."""
from __future__ import annotations
from core.types import DialogContext


class IDialogManager:
    def build_context(self) -> DialogContext:
        raise NotImplementedError
