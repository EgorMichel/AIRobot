"""Integration tests for module interoperability (passing stubs).

These tests use fake implementations to validate wiring between layers:
- driver -> kinematics -> safety -> robot tools
- LLM mode -> intent parser -> intent safety -> skill executor
"""
from __future__ import annotations
import pytest
from core.types import (
    Result,
    Joints,
    Pose,
    MoveHandle,
    RobotState,
    Intent,
    ExecutionReport,
    Error,
)
from drivers.base import IRobotDriver
from kinematics.base import IKinematics
from safety.base import ISafetyRules
from tools.robot_tools import RobotTools
from modes.llm_mode import LLMMode
from voice.intent_parser import IIntentParser
from voice.intent_safety import IIntentSafety
from skills.executor import ISkillExecutor
from core.types import Event


# --- Fakes for lower layers ---
class FakeDriver(IRobotDriver):
    def __init__(self):
        self.joints = Joints([0.0, 0.0, 0.0])
        self.last_cartesian = None
        self.last_joint_goal = None

    def read_joints(self) -> Result[Joints]:
        return Result(ok=True, data=self.joints)

    def command_joint_goal(self, joints: Joints, speed: float, accel: float) -> Result[MoveHandle]:
        self.last_joint_goal = (joints, speed, accel)
        return Result(ok=True, data=MoveHandle("mh_joint"))

    def command_cartesian_goal(self, pose: Pose, speed: float, accel: float, frame: str = "base") -> Result[MoveHandle]:
        self.last_cartesian = (pose, speed, accel, frame)
        return Result(ok=True, data=MoveHandle("mh_cart"))

    def stop(self) -> Result[None]:
        return Result(ok=True, data=None)


class FakeKinematics(IKinematics):
    def fk(self, joints: Joints) -> Result[Pose]:
        return Result(ok=True, data=Pose(0, 0, 0, 0, 0, 0))

    def ik(self, pose: Pose, seed: Joints | None = None):
        return Result(ok=True, data=[Joints([1, 1, 1])])


class FakeSafety(ISafetyRules):
    def check_motion(self, goal, state: RobotState):
        return Result(ok=True, data=None)


# --- Fakes for LLM pipeline ---
class FakeIntentParser(IIntentParser):
    def __init__(self, intent: Intent | None):
        self.intent = intent

    def parse(self, user_text: str, context):
        return self.intent


class FakeIntentSafety(IIntentSafety):
    def __init__(self, ok: bool = True):
        self.ok = ok

    def validate(self, intent: Intent, state: RobotState):
        if self.ok:
            return Result(ok=True, data=None)
        return Result(ok=False, error=Error(code="safety", message="blocked"))


class FakeSkillExecutor(ISkillExecutor):
    def __init__(self):
        self.executed: Intent | None = None

    def execute(self, intent: Intent):
        self.executed = intent
        return Result(ok=True, data=ExecutionReport(status="done"))


# --- Tests ---

def test_robot_tools_joint_and_cartesian_paths():
    driver = FakeDriver()
    kin = FakeKinematics()
    safe = FakeSafety()
    tools = RobotTools(driver, kin, safe)

    # cartesian path via Pose
    pose = Pose(1, 2, 3, 0.1, 0.2, 0.3)
    res1 = tools.move_p2p(pose, speed=0.5, accel=0.2)
    assert res1.ok
    assert driver.last_cartesian is not None

    # joint path via Joints
    joints = Joints([0.1, 0.2, 0.3])
    res2 = tools.move_p2p(joints, speed=0.5, accel=0.2)
    assert res2.ok
    assert driver.last_joint_goal is not None


def test_robot_tools_state_and_fk_usage():
    driver = FakeDriver()
    kin = FakeKinematics()
    safe = FakeSafety()
    tools = RobotTools(driver, kin, safe)

    state_res = tools.get_state()
    assert state_res.ok
    assert state_res.data is not None
    assert state_res.data.joints is not None
    assert state_res.data.tcp is not None


def test_llm_mode_executes_intent_when_safe():
    parser = FakeIntentParser(Intent(type="move_p2p", params={"target": "dummy"}))
    safety = FakeIntentSafety(ok=True)
    executor = FakeSkillExecutor()
    mode = LLMMode(parser, safety, executor)
    mode.enter({"state_cache": type("SC", (), {"get": lambda self=None: RobotState(joints=None, tcp=None)})()})

    mode.handle_event(Event(name="user_text", payload={"text": "go"}))
    assert executor.executed is not None


def test_llm_mode_blocks_when_safety_fails():
    parser = FakeIntentParser(Intent(type="move_p2p", params={"target": "dummy"}))
    safety = FakeIntentSafety(ok=False)
    executor = FakeSkillExecutor()
    mode = LLMMode(parser, safety, executor)
    mode.enter({"state_cache": type("SC", (), {"get": lambda self=None: RobotState(joints=None, tcp=None)})()})

    mode.handle_event(Event(name="user_text", payload={"text": "go"}))
    assert executor.executed is None
