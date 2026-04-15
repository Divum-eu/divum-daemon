from pydantic import BaseModel, Field
from enum import Enum

class Status(str, Enum):
    CREATED = "created"
    RESTARTING = "restarting"
    RUNNING = "running"
    PAUSED = "paused"
    EXITED = "exited"
    DEAD = "dead"

class MinecraftServerStatus(BaseModel):
    # status of the minecraft instance according to the ServerManager's API
    status: Status = Field(...)

    # last lines of the log from the minecraft instance
    log: str = Field(...)