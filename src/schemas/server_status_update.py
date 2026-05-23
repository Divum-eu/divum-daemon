from pydantic import BaseModel, Field

class ServerStatusUpdate(BaseModel):
    server_id: str = Field(...)
    status: str = Field(...)
    cpu_percent: float = Field(...)
    memory_usage_mb: int = Field(...)
    memory_limit_mb: int = Field(...)
    player_count: int | None = Field(default=None)
    player_max: int | None = Field(default=None)
