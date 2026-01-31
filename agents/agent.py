"""LLM-based agent implementation that uses a ReAct loop."""
import inspect
import json
from typing import List, Optional

import httpx

from agents.base import IAgent
from core.types import AgentMessage, Result, ToolCall
from tools.robot_tools import RobotTools


class LLMAgent(IAgent):
    def __init__(self, robot_tools: RobotTools, api_url: str, api_key: Optional[str] = None, model: Optional[str] = None, debug_logging: bool = False):
        if not api_url:
            raise ValueError("LLM_API_URL is required.")
        self.robot_tools = robot_tools
        self.api_url = self._resolve_llm_url(api_url)
        self.api_key = api_key
        self.model = model
        self.debug_logging = debug_logging
        self.system_prompt = self._build_system_prompt()
        print(f"[agent-config] LLM endpoint: {self.api_url}")

    def _resolve_llm_url(self, base_url: str) -> str:
        """Helper to append the standard chat completions path if not present."""
        url = base_url.rstrip("/")
        if not (url.endswith("/chat/completions")):
            # Simple check for common base paths
            if url.endswith("/api") or url.endswith("/api/v1"):
                 url += "/chat/completions"
            # Add more specific provider checks if needed
        return url

    def _get_tool_definitions(self) -> List[dict]:
        """Inspects RobotTools and generates a JSON schema for each tool."""
        tools = []
        for name, method in inspect.getmembers(self.robot_tools, predicate=inspect.iscoroutinefunction):
            if name.startswith('_'):
                continue
            
            doc = inspect.getdoc(method) or "No description."
            
            # A simple parser for the docstring to extract param descriptions
            param_docs = {}
            if doc:
                for line in doc.split('\n'):
                    if line.strip().startswith(':param'):
                        parts = line.strip().split(':', 2)
                        if len(parts) == 3:
                            param_name = parts[1].split(' ')[1]
                            param_desc = parts[2].strip()
                            param_docs[param_name] = param_desc

            sig = inspect.signature(method)
            properties = {}
            required = []
            for param in sig.parameters.values():
                if param.name == 'self':
                    continue
                
                param_type = "string"  # Default
                if param.annotation is not inspect.Parameter.empty:
                    # Convert annotation to string to handle forward references ('int' vs int)
                    annotation_str = str(param.annotation)
                    if 'int' in annotation_str or 'float' in annotation_str:
                        param_type = "number"
                    elif 'bool' in annotation_str:
                        param_type = "boolean"
                
                properties[param.name] = {
                    "type": param_type,
                    "description": param_docs.get(param.name, "")
                }
                if param.default is inspect.Parameter.empty:
                    required.append(param.name)

            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": doc.split('\n')[0],
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            })
        return tools

    def _build_system_prompt(self) -> str:
        return """
You are a helpful and brilliant robot control assistant. Your goal is to achieve the user's request by calling a sequence of available tools.

On each turn, you must think about your next step and then call ONE or MORE tools.
- **Think**: First, reason about the user's request, your previous actions, and the results you observed. Form a plan for what to do next.
- **Act**: Based on your thoughts, decide which tool(s) to call. You can call multiple tools in parallel if it makes sense.

You have access to the following tools:
{tools}

When you believe the user's request is fully complete, or if the user asks to finish, you MUST call the `shutdown` tool with a final summary for the user as the 'reason'.
Do not ask the user for clarification. Infer any missing details from the context or by using tools to gather more information.
Respond in the format specified by the user.
"""

    async def run(self, messages: List[AgentMessage]) -> Result[AgentMessage]:
        """Runs a single step of the agent's reasoning loop."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Convert our AgentMessage format to the one expected by the LLM API
        api_messages = [msg.to_dict() for msg in messages]

        payload = {
            "model": self.model,
            "messages": api_messages,
            "tools": self._get_tool_definitions(),
        }

        try:
            if self.debug_logging:
                print(f"[agent-debug] Sending payload to LLM: {json.dumps(payload, indent=2)}")
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.api_url, json=payload, headers=headers, timeout=60)
                resp.raise_for_status()
            
            # Read raw bytes and decode manually to avoid any streaming issues
            raw_text = resp.content.decode('utf-8')
            if self.debug_logging:
                print(f"[agent-debug] Raw LLM response text: {raw_text}")

            if not raw_text:
                return Result.err("llm_error", "LLM returned an empty response.")

            data = json.loads(raw_text)
            response_message = data.get("choices", [{}])[0].get("message", {})

            # The LLM should respond with tool calls
            if "tool_calls" in response_message and response_message["tool_calls"]:
                tool_calls = []
                for tc in response_message["tool_calls"]:
                    args_str = tc["function"]["arguments"]
                    try:
                        args = json.loads(args_str) if args_str else {}
                    except json.JSONDecodeError:
                        print(f"[warn] Failed to decode tool arguments: {args_str}. Using empty args.")
                        args = {}
                    tool_calls.append(ToolCall(id=tc["id"], name=tc["function"]["name"], args=args))
                return Result.ok(AgentMessage(role="assistant", content="", tool_calls=tool_calls))
            else:
                # If no tool call, it's a final answer
                return Result.ok(AgentMessage(role="assistant", content=response_message.get("content")))

        except json.JSONDecodeError as e:
             return Result.err("llm_error", f"LLM API call failed: Failed to decode JSON. Error: {e}. Response: {raw_text}")
        except Exception as e:
            return Result.err("llm_error", f"LLM API call failed: {e}")