from pydantic import BaseModel, Field

class WatchCommand(BaseModel):
    type: str = Field(...)  # "watch" or "unwatch"
    server_id: str = Field(...)
