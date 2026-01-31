"""Skill executor that maps intents to robot tool calls."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Any, Dict

import asyncio
from core.types import ExecutionReport, Intent, Result, ToolCall
from tools.robot_tools import RobotTools
from state.cache import StateCache


class ISkillExecutor(ABC):
    """Abstract interface for a component that executes intents."""

    @abstractmethod
    async def execute_tool_call(self, tool_call: ToolCall) -> Result:
        """Executes a single tool call."""
        raise NotImplementedError


class SkillExecutor(ISkillExecutor):
    """
    A concrete implementation of ISkillExecutor that maps intent types
    to methods of the RobotTools class.
    """

    def __init__(self, robot_tools: RobotTools, state_cache: StateCache):
        self.robot_tools = robot_tools
        self.state_cache = state_cache
        self.skill_map: Dict[str, Callable[..., Result[Any]]] = self._build_skill_map()

    def _build_skill_map(self) -> Dict[str, Callable[..., Result[Any]]]:
        """Creates a mapping from intent types to robot tool methods."""
        return {
            "get_tcp_pose": self.robot_tools.get_tcp_pose,
            "get_joint_positions": self.robot_tools.get_joint_positions,
            "get_state": self.robot_tools.get_state,
            "move_p2p_pose": self.robot_tools.move_p2p,
            "move_p2p_joints": self.robot_tools.move_p2p,
            "set_gripper": self.robot_tools.set_gripper,
            "stop": self.robot_tools.stop,
            "run_fk": self.robot_tools.run_fk,
            "run_ik": self.robot_tools.run_ik,
            "set_servo_angle": self.robot_tools.set_servo_angle,
        }

    async def execute_tool_call(self, tool_call: ToolCall) -> Result:
        """Executes a tool call by looking it up in the skill map."""
        print(f"[executor] Executing tool: {tool_call.name} with args: {tool_call.args}")
        
        skill_func = self.skill_map.get(tool_call.name)
        if not skill_func:
            err_msg = f"Unknown tool: '{tool_call.name}'"
            print(f"[error] {err_msg}")
            return Result.err(code="tool_not_found", message=err_msg)

        try:
            # Await the coroutine function with the provided arguments
            result = await skill_func(**tool_call.args)
            return result
        except TypeError as e:
            err_msg = f"Invalid parameters for tool '{tool_call.name}': {e}"
            print(f"[error] {err_msg}")
            return Result.err(code="invalid_params", message=err_msg)
        except Exception as e:
            err_msg = f"An unexpected error occurred during tool execution: {e}"
            print(f"[error] {err_msg}")
            return Result.err(code="execution_failed", message=err_msg)
