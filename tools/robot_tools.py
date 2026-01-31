"""MCP Robot tools stub (wraps driver + kinematics + safety)."""
from __future__ import annotations
from typing import Optional, Union
from core.types import ExecutionReport, Joints, MoveHandle, Pose, Result
from drivers.base import IRobotDriver, IServo
from kinematics.base import IKinematics
from safety.base import ISafetyRules


class RobotTools:
    def __init__(self, driver: IRobotDriver, kinematics: IKinematics, safety: ISafetyRules, servo: IServo):
        self.driver = driver
        self.kinematics = kinematics
        self.safety = safety
        self.servo = servo

    async def get_joint_positions(self) -> Result[Joints]:
        """Gets the current angular positions of all robot joints."""
        return await self.driver.read_joints()

    async def get_tcp_pose(self, frame: str = "base") -> Result[Pose]:
        """
        Gets the current Tool Center Point (TCP) pose relative to a coordinate frame.
        :param frame: The reference coordinate frame, defaults to "base".
        """
        joints_res = await self.driver.read_joints()
        if not joints_res.ok:
            return joints_res
        return await self.kinematics.fk(joints_res.data)

    async def move_p2p(self, target: Union[Pose, Joints], speed: float, accel: float, frame: str = "base") -> Result[MoveHandle]:
        """
        Moves the robot to a target point in a point-to-point (P2P) manner.
        :param target: The destination, specified as either a Cartesian Pose or a set of joint angles (Joints).
        :param speed: The desired movement speed.
        :param accel: The desired movement acceleration.
        :param frame: The reference frame if the target is a Pose, defaults to "base".
        """
        state_res = await self.get_state()
        if not state_res.ok:
            return state_res
        
        check = await self.safety.check_motion(target, state_res.data)
        if not check.ok:
            return check
            
        if isinstance(target, Pose):
            return await self.driver.command_cartesian_goal(target, speed, accel, frame)
        return await self.driver.command_joint_goal(target, speed, accel)

    async def stop(self) -> Result[None]:
        """Stops all robot motion immediately."""
        return await self.driver.stop()

    async def set_gripper(self, state: str, force: Optional[float] = None) -> Result[None]:
        """
        Controls the gripper.
        :param state: The desired state, either "open" or "closed".
        :param force: The grasping force to apply, if applicable.
        """
        print(f"[robot-tool-dummy] Setting gripper to {state} with force {force}")
        return Result.ok(None)

    def set_speed_profile(self, profile) -> Result[None]:  # type: ignore
        return Result(ok=False, error=None)  # stub

    async def run_fk(self, joints: Joints) -> Result[Pose]:
        """Runs forward kinematics to calculate a Pose from joint angles."""
        return await self.kinematics.fk(joints)

    async def run_ik(self, pose: Pose, seed: Optional[Joints] = None) -> Result[List[Joints]]:
        """Runs inverse kinematics to find joint solutions for a given Pose."""
        return await self.kinematics.ik(pose, seed)

    async def get_state(self) -> Result[RobotState]:
        """Retrieves the full current state of the robot (joints, pose, etc.)."""
        joints_res = await self.driver.read_joints()
        if not joints_res.ok:
            return Result.err(joints_res.error.code, joints_res.error.message)
            
        pose_res = await self.kinematics.fk(joints_res.data)
        if not pose_res.ok:
            return Result.err(pose_res.error.code, pose_res.error.message)
            
        from core.types import RobotState
        return Result.ok(RobotState(joints=joints_res.data, tcp=pose_res.data, mode="idle"))

    def heartbeat(self):
        return Result(ok=True, data=None)

    def get_limits(self):
        return Result(ok=True, data=None)

    async def shutdown(self, reason: str = "Команда от ассистента") -> Result[dict]:
        """
        Initiates the shutdown of the application. Call this when the user's task is fully complete.
        :param reason: The reason for shutting down.
        """
        # This tool doesn't do anything itself, its call is intercepted by the mode.
        return Result.ok({"status": "shutdown_initiated", "reason": reason})

    async def set_servo_angle(self, angle: int) -> Result[dict]:
        """
        Sets the angle of a single servo motor.
        :param angle: The desired angle for the servo, from 0 to 180 degrees.
        """
        try:
            angle = int(angle)
        except (ValueError, TypeError):
            return Result.err("invalid_angle", f"Angle must be a valid integer, but got '{angle}'.")

        if not 0 <= angle <= 180:
            return Result.err("invalid_angle", "Angle must be between 0 and 180.")

        success = await self.run_in_executor(self.servo.set_angle, angle)

        if success:
            return Result.ok({"status": "done"})
        else:
            return Result.err("servo_error", "Failed to set servo angle.")

    @staticmethod
    async def run_in_executor(func, *args):
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, func, *args)
