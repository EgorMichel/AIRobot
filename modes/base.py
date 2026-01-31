"""Control modes base definitions."""
from __future__ import annotations
from typing import Protocol
from core.types import Event, ModeContext


class IControlMode(Protocol):
    async def enter(self, ctx: ModeContext) -> None: ...
    async def handle_event(self, event: Event) -> None: ...
    async def tick(self) -> None: ...
    async def exit(self) -> None: ...


class ModeManager:
    def __init__(self):
        self.modes = {}
        self.current: IControlMode | None = None
        self.ctx: ModeContext = {}

    def register(self, name: str, mode: IControlMode):
        self.modes[name] = mode

    async def switch(self, name: str):
        if self.current:
            await self.current.exit()
        self.current = self.modes.get(name)
        if not self.current:
            raise ValueError(f"Mode {name} not registered")
        await self.current.enter(self.ctx)

    async def dispatch_event(self, event: Event):
        if self.current:
            await self.current.handle_event(event)

    async def tick(self):
        if self.current:
            await self.current.tick()

    def get_current_mode(self) -> IControlMode | None:
        return self.current
