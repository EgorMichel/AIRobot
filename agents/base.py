"""Base protocols for ReAct-style agents."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List
from core.types import AgentMessage, Result


class IAgent(ABC):
    """Abstract interface for a ReAct agent."""

    @abstractmethod
    async def run(self, messages: List[AgentMessage]) -> Result[AgentMessage]:
        """
        Runs a single step of the agent's reasoning loop.
        :param messages: The history of the conversation and actions.
        :return: The agent's next message, containing thoughts and/or tool calls.
        """
        ...