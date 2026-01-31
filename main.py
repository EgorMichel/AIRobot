"""
Main entry point for the voice-controlled robotic manipulator application.

This script initializes all the necessary components based on the defined architecture,
loads configuration from environment variables, and starts the main application loop.
"""
import os
import sys
from dotenv import load_dotenv

# # Add project root to Python path
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))


import asyncio
import sys
from core.types import RobotState
from voice.asr import SpeechRecognitionInput
from voice.tts import GTTSOutput, ConsoleOutput
from modes.base import ModeManager
from modes.llm_mode import LLMMode
from skills.executor import SkillExecutor
from agents.agent import LLMAgent
from tools.robot_tools import RobotTools
from safety.base import ISafetyRules
from state.cache import StateCache
from drivers.base import IRobotDriver, IServo
from drivers.servo_driver import ServoController, MockServo
from kinematics.base import IKinematics


# Dummy implementations for components that are not the focus of this example
class ConsoleSafety(ISafetyRules):
    async def check_motion(self, goal, state) -> "Result[None]":
        print(f"[safety-dummy] Checking motion for goal: {goal}")
        from core.types import Result
        return Result.ok(None)

class DummyRobot(IRobotDriver):
    async def read_joints(self) -> "Result[Joints]":
        from core.types import Result, Joints
        print("[robot-dummy] Reading joints")
        return Result.ok(Joints([0.0] * 6))

    async def command_joint_goal(self, joints, speed, accel) -> "Result[MoveHandle]":
        from core.types import Result, MoveHandle
        print(f"[robot-dummy] Moving to joints: {joints}")
        return Result.ok(MoveHandle("dummy-move-123"))
    
    async def command_cartesian_goal(self, pose, speed, accel, frame) -> "Result[MoveHandle]":
        from core.types import Result, MoveHandle
        print(f"[robot-dummy] Moving to pose: {pose}")
        return Result.ok(MoveHandle("dummy-move-123"))

    async def stop(self) -> "Result[None]":
        from core.types import Result
        print("[robot-dummy] Stopping")
        return Result.ok(None)

class DummyKinematics(IKinematics):
    async def fk(self, joints: "Joints") -> "Result[Pose]":
        from core.types import Result, Pose
        print(f"[kinematics-dummy] Forward kinematics for: {joints}")
        return Result.ok(Pose(x=100, y=100, z=100, rx=0, ry=0, rz=0))

    async def ik(self, pose: "Pose", seed=None) -> "Result[list[Joints]]":
        from core.types import Result, Joints
        print(f"[kinematics-dummy] Inverse kinematics for: {pose}")
        return Result.ok([Joints([0.1] * 6)])


async def main():
    """
    Initializes and runs the voice control application.
    """
    print("Starting voice-controlled manipulator application...")
    load_dotenv()

    # --- 1. Load Configuration ---
    llm_api_url = os.getenv("LLM_API_URL")
    llm_api_key = os.getenv("LLM_API_KEY")
    llm_model = os.getenv("LLM_MODEL")
    mic_index_raw = os.getenv("MIC_DEVICE_INDEX")
    mic_device_index = int(mic_index_raw) if mic_index_raw is not None else None
    tts_enabled = os.getenv("TTS_ENABLED", "true").lower() == "true"
    servo_enabled = os.getenv("SERVO_ENABLED", "false").lower() == "true"
    llm_debug_logging = os.getenv("LLM_DEBUG_LOGGING", "false").lower() == "true"
    servo_port = os.getenv("SERVO_PORT") or None

    if not llm_api_url:
        print("[error] LLM_API_URL is not set. Please define it in your .env file.")
        sys.exit(1)

    # --- 2. Initialize Architectural Components ---
    
    voice_input = SpeechRecognitionInput(mic_device_index=mic_device_index)
    if tts_enabled:
        voice_output = GTTSOutput()
    else:
        print("[config] TTS is disabled. Using console output.")
        voice_output = ConsoleOutput()
    state_cache = StateCache()
    robot_driver = DummyRobot()
    kinematics_solver = DummyKinematics()
    safety_rules = ConsoleSafety()

    # --- 2.1. Initialize Servo ---
    servo_driver: IServo
    if servo_enabled:
        try:
            print(f"[config] Real servo is enabled (Port: {servo_port or 'auto'}).")
            servo_driver = ServoController(port=servo_port)
        except Exception as e:
            print(f"[error] Failed to initialize real servo: {e}")
            print("[config] Falling back to mock servo.")
            servo_driver = MockServo()
    else:
        print("[config] Servo is disabled. Using mock servo.")
        servo_driver = MockServo()
    
    robot_tools = RobotTools(
        driver=robot_driver,
        kinematics=kinematics_solver,
        safety=safety_rules,
        servo=servo_driver,
    )
    
    agent = LLMAgent(
        robot_tools=robot_tools,
        api_url=llm_api_url,
        api_key=llm_api_key,
        model=llm_model,
        debug_logging=llm_debug_logging,
    )
    skill_executor = SkillExecutor(robot_tools=robot_tools, state_cache=state_cache)

    # --- 3. Initialize Control Modes ---
    mode_manager = ModeManager()
    
    llm_mode = LLMMode(
        agent=agent,
        skill_executor=skill_executor,
        voice_in=voice_input,
        voice_out=voice_output,
    )
    mode_manager.register("llm", llm_mode)
    
    # --- 4. Setup Signal Handling for Graceful Shutdown ---
    loop = asyncio.get_running_loop()
    
    def shutdown_handler():
        print("\nShutdown signal received.")
        current_mode = mode_manager.get_current_mode()
        if hasattr(current_mode, 'stop_loop'):
            current_mode.stop_loop()

    # For Windows, SIGINT is tricky. We'll rely on the try/except in the loop for Ctrl+C.
    # For Linux/macOS, this is more robust.
    try:
        import signal
        loop.add_signal_handler(signal.SIGINT, shutdown_handler)
    except (ImportError, AttributeError, NotImplementedError, RuntimeError):
        print("[warn] Signal handlers not available on this system. Use Ctrl+C in the console to exit.")

    # --- 5. Start Application ---
    main_task = None
    try:
        print("Switching to LLM mode. Press Enter to start listening, Ctrl+C to exit.")
        await mode_manager.switch("llm")
        
        current_mode = mode_manager.get_current_mode()
        if hasattr(current_mode, 'run_interactive_loop'):
            main_task = loop.create_task(current_mode.run_interactive_loop())
            await main_task
        else:
            print("[warn] Current mode does not have a 'run_interactive_loop' method. Application will exit.")

    except asyncio.CancelledError:
        print("\nMain task cancelled.")
    finally:
        if main_task and not main_task.done():
            main_task.cancel()
        
        print("\nApplication shutting down.")
        current_mode = mode_manager.get_current_mode()
        if current_mode:
            await current_mode.exit()
        
        # Clean up servo connection
        if servo_driver:
            servo_driver.close()
            
        print("Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())