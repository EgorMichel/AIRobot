"""Kinematics protocol stub."""
from __future__ import annotations
from typing import List, Optional, Protocol
from core.types import Joints, Pose, Result


class IKinematics(Protocol):
    async def fk(self, joints: Joints) -> Result[Pose]: ...
    async def ik(self, pose: Pose, seed: Optional[Joints] = None) -> Result[List[Joints]]: ...
