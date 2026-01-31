"""
New integration tests for the main ReAct-based application flow.

These tests validate the correct orchestration of the LLMMode, Agent, and Tools.
"""
import asyncio
import json
from typing import List, Dict, Any, Optional

import pytest
from core.types import AgentMessage, Result, ToolCall
from agents.base import IAgent
from skills.executor import SkillExecutor
from tools.robot_tools import RobotTools
from voice.asr import IVoiceInput
from voice.tts import IVoiceOutput
from modes.llm_mode import LLMMode
from state.cache import StateCache

# Import dummy/mock components from the application
from main import DummyRobot, DummyKinematics, ConsoleSafety
from drivers.servo_driver import MockServo

# --- Fakes for Testing ---

class FakeVoiceInput(IVoiceInput):
    """A fake voice input that returns a pre-set text."""
    def __init__(self, text_to_return: str):
        self._text = text_to_return

    async def listen_once(self) -> str:
        print(f"[fake-voice-in] Heard: '{self._text}'")
        return self._text
    
    # Unused methods
    async def start(self): pass
    async def stop(self): pass
    def on_text(self, callback): pass

class FakeVoiceOutput(IVoiceOutput):
    """A fake voice output that stores spoken text instead of playing it."""
    def __init__(self):
        self.spoken_text: List[str] = []

    async def speak(self, text: str):
        print(f"[fake-voice-out] Said: '{text}'")
        self.spoken_text.append(text)

class FakeAgent(IAgent):
    """
    A mock agent that returns a pre-programmed sequence of responses.
    This is the key to testing the ReAct loop.
    """
    def __init__(self):
        # A list of responses to return in order
        self.responses: List[Result[AgentMessage]] = []
        # A record of message histories received by the agent
        self.received_histories: List[List[AgentMessage]] = []
        self._response_index = 0

    def add_response(self, message: AgentMessage, is_error: bool = False):
        """Adds a successful or error response to the queue."""
        if is_error:
            self.responses.append(Result.err("fake_agent_error", message.content))
        else:
            self.responses.append(Result.ok(message))

    async def run(self, messages: List[AgentMessage]) -> Result[AgentMessage]:
        """Returns the next pre-programmed response."""
        self.received_histories.append(messages.copy())
        if self._response_index < len(self.responses):
            response = self.responses[self._response_index]
            self._response_index += 1
            return response
        # Default to a stop message if we run out of programmed responses
        return Result.ok(AgentMessage(role="assistant", content="No more programmed responses."))

# --- Pytest Fixtures ---

@pytest.fixture
def fake_voice_out():
    return FakeVoiceOutput()

@pytest.fixture
def fake_agent():
    return FakeAgent()

@pytest.fixture
def llm_mode(fake_agent, fake_voice_out):
    """Sets up the LLMMode with all fake/dummy components."""
    state_cache = StateCache()
    robot_driver = DummyRobot()
    kinematics_solver = DummyKinematics()
    safety_rules = ConsoleSafety()
    servo_driver = MockServo()
    
    robot_tools = RobotTools(
        driver=robot_driver,
        kinematics=kinematics_solver,
        safety=safety_rules,
        servo=servo_driver,
    )
    
    skill_executor = SkillExecutor(robot_tools=robot_tools, state_cache=state_cache)
    
    # We need a voice input, but it will be replaced in each test
    dummy_voice_in = FakeVoiceInput("")

    mode = LLMMode(
        agent=fake_agent,
        skill_executor=skill_executor,
        voice_in=dummy_voice_in,
        voice_out=fake_voice_out,
        max_retries=1, # Use only 1 retry for predictable tests
    )
    
    # Manually enter the mode
    asyncio.run(mode.enter({}))
    
    return mode

# --- Tests ---

@pytest.mark.asyncio
async def test_single_turn_conversation(llm_mode, fake_agent, fake_voice_out):
    """
    Tests a simple flow: User asks -> Agent gives a final answer immediately.
    """
    # Arrange
    llm_mode.history.clear()
    user_request = "Hello, robot!"
    final_answer = "Hello there! How can I help?"
    
    llm_mode.voice_in = FakeVoiceInput(user_request)
    fake_agent.add_response(AgentMessage(role="assistant", content=final_answer))
    
    # Act
    await llm_mode._run_agent_loop(user_request)
    
    # Assert
    # Check that the agent received the correct history
    assert len(fake_agent.received_histories) == 1
    assert fake_agent.received_histories[0][-1].role == "user"
    assert fake_agent.received_histories[0][-1].content == user_request
    
    # Check that the final answer was spoken
    assert final_answer in fake_voice_out.spoken_text

@pytest.mark.asyncio
async def test_multi_step_react_loop_success(llm_mode, fake_agent, fake_voice_out):
    """
    Tests a successful multi-step ReAct loop:
    1. User asks for TCP pose.
    2. Agent calls `get_joint_positions`.
    3. Agent receives joint positions and calls `run_fk`.
    4. Agent receives the pose and gives the final answer.
    """
    # Arrange
    llm_mode.history.clear()
    user_request = "What's your current TCP pose?"
    
    # Step 1: Agent decides to get joints first
    agent_response_1 = AgentMessage(
        role="assistant",
        tool_calls=[ToolCall(id="call_1", name="get_joint_positions", args={})]
    )
    fake_agent.add_response(agent_response_1)

    # Step 2: Agent receives joints and calls fk
    agent_response_2 = AgentMessage(
        role="assistant",
        tool_calls=[ToolCall(id="call_2", name="run_fk", args={"joints": {"values": [0.0] * 6}})]
    )
    fake_agent.add_response(agent_response_2)

    # Step 3: Agent receives pose and gives final answer
    final_answer = "The TCP pose is at X=100, Y=100, Z=100."
    agent_response_3 = AgentMessage(role="assistant", content=final_answer)
    fake_agent.add_response(agent_response_3)

    llm_mode.voice_in = FakeVoiceInput(user_request)

    # Act
    await llm_mode._run_agent_loop(user_request)

    # Assert
    # 1. Agent was called 3 times
    assert len(fake_agent.received_histories) == 3
    
    # 2. Check the history of the second call (it should contain the result of get_joint_positions)
    history_2 = fake_agent.received_histories[1]
    assert history_2[-1].role == "tool"
    assert history_2[-1].tool_call_id == "call_1"
    tool_result_1 = json.loads(history_2[-1].content)
    assert tool_result_1["values"] == [0.0] * 6

    # 3. Check the history of the third call (it should contain the result of run_fk)
    history_3 = fake_agent.received_histories[2]
    assert history_3[-1].role == "tool"
    assert history_3[-1].tool_call_id == "call_2"
    tool_result_2 = json.loads(history_3[-1].content)
    assert tool_result_2["x"] == 100
    
    # 4. Final answer was spoken
    assert final_answer in fake_voice_out.spoken_text

@pytest.mark.asyncio
async def test_tool_execution_error_handling(llm_mode, fake_agent, fake_voice_out):
    """
    Tests that if a tool call fails, the error is reported back to the agent.
    """
    # Arrange
    llm_mode.history.clear()
    user_request = "Set servo to an invalid angle."
    
    # Step 1: Agent calls a tool with invalid arguments
    agent_response_1 = AgentMessage(
        role="assistant",
        tool_calls=[ToolCall(id="call_1", name="set_servo_angle", args={"angle": 999})] # Invalid angle
    )
    fake_agent.add_response(agent_response_1)
    
    # Step 2: Agent sees the error and reports it
    final_answer = "I couldn't set that angle because it's out of range."
    agent_response_2 = AgentMessage(role="assistant", content=final_answer)
    fake_agent.add_response(agent_response_2)

    llm_mode.voice_in = FakeVoiceInput(user_request)

    # Act
    await llm_mode._run_agent_loop(user_request)

    # Assert
    # 1. Agent was called twice
    assert len(fake_agent.received_histories) == 2
    
    # 2. Check that the second history contains the tool error
    history_2 = fake_agent.received_histories[1]
    assert history_2[-1].role == "tool"
    assert "Error: Angle must be between 0 and 180" in history_2[-1].content
    
    # 3. The agent's final explanation was spoken
    assert final_answer in fake_voice_out.spoken_text

@pytest.mark.asyncio
async def test_shutdown_tool_call(llm_mode, fake_agent, fake_voice_out):
    """
    Tests that calling the `shutdown` tool stops the loop and speaks the reason.
    """
    # Arrange
    llm_mode.history.clear()
    user_request = "We are done, shut down."
    shutdown_reason = "Task complete."
    
    agent_response = AgentMessage(
        role="assistant",
        tool_calls=[ToolCall(id="call_1", name="shutdown", args={"reason": shutdown_reason})]
    )
    fake_agent.add_response(agent_response)

    llm_mode.voice_in = FakeVoiceInput(user_request)
    
    # Act
    await llm_mode._run_agent_loop(user_request)
    
    # Assert
    # 1. The shutdown reason was spoken
    assert shutdown_reason in fake_voice_out.spoken_text
    
    # 2. The mode's running flag is set to False
    assert llm_mode._is_running is False

@pytest.mark.asyncio
async def test_agent_error_handling(llm_mode, fake_agent, fake_voice_out):
    """
    Tests that if the agent itself returns an error, it is spoken to the user.
    """
    # Arrange
    llm_mode.history.clear()
    user_request = "What if you fail?"
    error_message = "I have malfunctioned."
    
    # FakeAgent is programmed to return an error immediately
    fake_agent.add_response(AgentMessage(role="assistant", content=error_message), is_error=True)

    llm_mode.voice_in = FakeVoiceInput(user_request)
    
    # Act
    await llm_mode._run_agent_loop(user_request)

    # Assert
    # 1. The agent error message was spoken
    assert "Ошибка агента: I have malfunctioned." in fake_voice_out.spoken_text
    
    # 2. History should be preserved on agent error
    assert len(llm_mode.history) == 1
    assert llm_mode.history[0].role == "user"

@pytest.mark.asyncio
async def test_long_term_memory_conversation(llm_mode, fake_agent, fake_voice_out):
    """
    Tests that conversation history is maintained across separate agent loops.
    """
    # ARRANGE
    # Ensure history is clean before this multi-step test
    llm_mode.history.clear()
    
    # Interaction 1: User states their name
    request_1 = "My name is John."
    response_1 = AgentMessage(role="assistant", content="Okay, I will remember that.")
    
    # Interaction 2: User asks for their name
    request_2 = "What is my name?"
    response_2 = AgentMessage(role="assistant", content="Your name is John.")

    # Program the agent's responses
    fake_agent.add_response(response_1)
    fake_agent.add_response(response_2)

    # ACT
    # Run the first loop
    await llm_mode._run_agent_loop(request_1)

    # Run the second loop
    await llm_mode._run_agent_loop(request_2)

    # ASSERT
    # 1. Agent was called twice
    assert len(fake_agent.received_histories) == 2
    
    # 2. Check the history sent to the agent in the *second* call
    history_for_second_call = fake_agent.received_histories[1]
    
    # It should contain the full conversation:
    # [user: "My name is John", assistant: "Okay...", user: "What is my name?"]
    assert len(history_for_second_call) == 3
    assert history_for_second_call[0].role == "user"
    assert history_for_second_call[0].content == request_1
    assert history_for_second_call[1].role == "assistant"
    assert history_for_second_call[1].content == response_1.content
    assert history_for_second_call[2].role == "user"
    assert history_for_second_call[2].content == request_2

    # 3. Check that the final answer was spoken
    assert response_2.content in fake_voice_out.spoken_text