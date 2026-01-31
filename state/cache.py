"""State cache stub."""
from __future__ import annotations
from core.types import RobotState


class StateCache:
    def __init__(self):
        self._state = RobotState()

    def get(self) -> RobotState:
        return self._state

    def set(self, state: RobotState) -> None:
        self._state = state
