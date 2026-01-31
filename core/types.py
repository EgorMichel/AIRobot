"""Core type definitions for robot control architecture (skeleton).
All implementations are stubs; replace NotImplementedError with real logic.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from typing import Generic, List, Optional, Protocol, TypeVar, Union, Callable

T = TypeVar("T")


@dataclass
class Error:
    code: str
    message: str


@dataclass
class Result(Generic[T]):
    ok: bool
    data: Optional[T] = None
    error: Optional[Error] = None

    @classmethod
    def ok(cls, data: T) -> Result[T]:
        return cls(ok=True, data=data)

    @classmethod
    def err(cls, code: str, message: str) -> Result[T]:
        return cls(ok=False, error=Error(code=code, message=message))


@dataclass
class Pose:
    x: float
    y: float
    z: float
    rx: float
    ry: float
    rz: float
    frame: str = "base"

    def to_dict(self):
        return asdict(self)


@dataclass
class Joints:
    values: List[float]

    def to_dict(self):
        return asdict(self)


@dataclass
class RobotState:
    joints: Optional[Joints] = None
    tcp: Optional[Pose] = None
    mode: str = "idle"
    error: Optional[Error] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class MoveHandle:
    handle_id: str


@dataclass
class Intent:
    type: str
    params: Optional[dict] = None
    requires_confirmation: bool = False


@dataclass
class ExecutionReport:
    status: str
    detail: Optional[str] = None
    result: Optional[dict] = None


@dataclass
class Event:
    name: str
    payload: dict


@dataclass
class DialogContext:
    history: list = None
    state: Optional[RobotState] = None


class ILogger(Protocol):
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...


class IStateCache(Protocol):
    def get(self) -> RobotState: ...
    def set(self, state: RobotState) -> None: ...


ModeContext = dict


# Callable aliases
TextCallback = Callable[[str], None]


# --- ReAct Agent Types ---

@dataclass
class ToolCall:
    id: str
    name: str
    args: dict

@dataclass
class AgentMessage:
    role: str  # "user", "assistant", "tool"
    content: Optional[str] = None
    thought: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None # For non-standard APIs like polza.ai

    def to_dict(self):
        """Serializes the message to a dictionary for LLM API consumption."""
        d = {"role": self.role}
        
        # Only add content if it's not None
        if self.content is not None:
            d["content"] = self.content

        if self.tool_calls:
            d["tool_calls"] = [
                {"type": "function", "id": tc.id, "function": {"name": tc.name, "arguments": json.dumps(tc.args)}}
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        
        if self.name:
            d["name"] = self.name

        return d
