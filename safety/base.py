"""Safety rules protocol stub."""
from __future__ import annotations
from typing import Protocol, Union
from core.types import Pose, Joints, Result, RobotState


class ISafetyRules(Protocol):
    async def check_motion(self, goal: Union[Pose, Joints], state: RobotState) -> Result[None]: ...
