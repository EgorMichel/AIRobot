"""Logger stub (prints to stdout)."""
from __future__ import annotations
from core.types import ILogger


class Logger(ILogger):
    def info(self, msg: str) -> None:
        print(f"[INFO] {msg}")

    def warning(self, msg: str) -> None:
        print(f"[WARN] {msg}")

    def error(self, msg: str) -> None:
        print(f"[ERROR] {msg}")
