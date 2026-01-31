"""LLM-driven control mode that uses a ReAct agent for complex tasks."""
from __future__ import annotations
import asyncio
import json
import re
from typing import List

from agents.base import IAgent
from core.types import AgentMessage, ModeContext
from modes.base import IControlMode
from skills.executor import ISkillExecutor
from voice.asr import IVoiceInput
from voice.tts import IVoiceOutput


class LLMMode(IControlMode):
    """
    A control mode that uses a ReAct agent to interact with the user and the robot.
    """
    def __init__(
        self,
        agent: IAgent,
        skill_executor: ISkillExecutor,
        voice_in: IVoiceInput,
        voice_out: IVoiceOutput,
        max_retries: int = 3,
    ):
        self.agent = agent
        self.skill_executor = skill_executor
        self.voice_in = voice_in
        self.voice_out = voice_out
        self.max_retries = max_retries
        self.ctx: ModeContext = {}
        self._is_running = False
        self.history: List[AgentMessage] = []

    async def enter(self, ctx: ModeContext) -> None:
        self.ctx = ctx
        self._is_running = True
        print("[mode] Entered LLMMode.")
        await self.voice_out.speak("Режим агента активирован.")

    def _clean_text_for_tts(self, text: str) -> str:
        """Removes special characters, markdown, and emojis to make the text safe for TTS."""
        # This regex keeps Cyrillic, Latin, numbers, spaces, and basic punctuation.
        # It removes everything else, including emojis.
        cleaned_text = re.sub(r'[^a-zA-Zа-яА-Я0-9\s.,!?-]', '', text)
        return cleaned_text.strip()

    async def _run_agent_loop(self, initial_request: str):
        """Manages the ReAct loop with retries: User -> Agent -> Tools -> Agent -> User."""
        self.history.append(AgentMessage(role="user", content=initial_request))
        retries_left = self.max_retries

        while retries_left > 0:
            # 1. Get next action from agent
            agent_response_res = await self.agent.run(self.history)
            if not agent_response_res.ok:
                await self.voice_out.speak(f"Ошибка агента: {agent_response_res.error.message}")
                # Clear history on agent error to start fresh
                self.history.clear()
                return

            agent_message = agent_response_res.data
            self.history.append(agent_message)

            # 2. If agent provided a final answer, speak it and exit
            if agent_message.content:
                cleaned_response = self._clean_text_for_tts(agent_message.content)
                await self.voice_out.speak(cleaned_response)
                return

            # 3. If no tool calls, something is wrong
            if not agent_message.tool_calls:
                await self.voice_out.speak("Агент не вернул ни ответа, ни команды. Завершаю задачу.")
                return
            
            # 4. Check for shutdown command and execute tools
            has_errors = False
            # Check for shutdown command before execution
            for tc in agent_message.tool_calls:
                if tc.name == "shutdown":
                    print("[mode] Shutdown command received from agent.")
                    await self.voice_out.speak(tc.args.get("reason", "Завершаю работу по команде."))
                    self.stop_loop()
                    return

            tool_tasks = [self.skill_executor.execute_tool_call(tc) for tc in agent_message.tool_calls]
            tool_results = await asyncio.gather(*tool_tasks, return_exceptions=True)

            # 5. Append tool results to history and check for errors
            for i, result in enumerate(tool_results):
                tool_call_id = agent_message.tool_calls[i].id
                
                content = ""
                if isinstance(result, Exception):
                    content = f"Error executing tool: {result}"
                    has_errors = True
                else:
                    if result.ok:
                        # The content for a tool result MUST be a JSON-serializable string.
                        if hasattr(result.data, 'to_dict'):
                            content = json.dumps(result.data.to_dict(), indent=2)
                        else:
                            # Handles None -> "null", str -> "\"string\"", etc.
                            content = json.dumps(result.data)
                    else:
                        content = f"Error: {result.error.message}"
                        has_errors = True
                
                self.history.append(AgentMessage(role="tool", content=content, tool_call_id=tool_call_id))
            
            # 6. If there were errors, decrement retries and continue the loop
            if has_errors:
                retries_left -= 1
                print(f"[agent] A tool execution failed. Retries left: {retries_left}")
                if retries_left == 0:
                    await self.voice_out.speak("Не удалось выполнить команду после нескольких попыток.")
                continue # Go to the next agent loop iteration to let the agent see the error

        # If loop finishes without success (e.g. retries exhausted)
        if retries_left == 0:
             print("[agent] Task failed after maximum retries.")

    async def run_interactive_loop(self):
        """The main interactive loop for this mode."""
        while self._is_running:
            try:
                # This input call is blocking, which is not ideal in an async app,
                # but for a console PoC it's acceptable to signal the start of listening.
                await asyncio.to_thread(input, "\nPress Enter and start speaking...")
                
                user_text = await self.voice_in.listen_once()
                if not user_text:
                    continue
                
                # Start the agent loop for this request
                await self._run_agent_loop(user_text)

            except (KeyboardInterrupt, asyncio.CancelledError):
                print("\nInteractive loop interrupted.")
                self.stop_loop()
            except Exception as e:
                print(f"[error] An error occurred in the interactive loop: {e}")
                await self.voice_out.speak("Произошла системная ошибка.")

    def stop_loop(self):
        """Signals the interactive loop to stop."""
        if self._is_running:
            print("[mode] Stopping interactive loop...")
            self._is_running = False

    async def handle_event(self, event) -> None:
        pass

    async def tick(self) -> None:
        pass

    async def exit(self) -> None:
        print("[mode] Exiting LLMMode.")
        self.stop_loop() # Ensure loop is stopped on exit
        await self.voice_out.speak("Режим агента выключен.")

# Add a to_dict method to Result for serialization
def result_to_dict(self):
    return {
        "ok": self.ok,
        "data": self.data,
        "error": self.error.__dict__ if self.error else None,
    }

from core.types import Result
Result.to_dict = result_to_dict
