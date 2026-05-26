"""DTOs for a Minecraft server instance's status"""

from pydantic import BaseModel, Field
from enum import Enum


class Status(str, Enum):
    """Values for the Minecraft server instance's state"""
    CREATED = "created"
    RESTARTING = "restarting"
    RUNNING = "running"
    PAUSED = "paused"
    EXITED = "exited"
    DEAD = "dead"


class MinecraftServerStatus(BaseModel):
    """The Minecraft server instance's status"""

    status: Status = Field(...)
    player_count: int = Field(...)
    ram_usage_mb: int = Field(...)
    cpu_usage_percentage: float = Field(...)
