"""DTOs for a Minecraft server instance's status"""

from pydantic import BaseModel, Field
from enum import Enum


class MinecraftDockerContainerStatus(str, Enum):
    """Values for the Minecraft server instance's docker container state."""

    CREATED = "created"
    RESTARTING = "restarting"
    RUNNING = "running"
    PAUSED = "paused"
    EXITED = "exited"
    DEAD = "dead"

class MinecraftServerInstanceStatus(str, Enum):
    """Values for the Minecraft server instance's state."""

    STARTING = "starting"
    RESTARTING = "restarting"
    RUNNING = "running"
    STOPPED = "stopped"

class MinecraftServerStatus(BaseModel):
    """The Minecraft server instance's status"""

    status: MinecraftServerInstanceStatus = Field(...)
    player_count: int = Field(...)
    ram_usage_mb: int = Field(...)
    cpu_usage_percentage: float = Field(...)
    ram_usage_limit_mb: int = Field(...)
    cpu_usage_limit_percentage: float = Field(...)
