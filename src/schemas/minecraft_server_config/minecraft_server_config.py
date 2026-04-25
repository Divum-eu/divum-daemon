import os
import re
from abc import ABC, abstractmethod

import psutil
from pydantic import BaseModel, Field, field_validator

from utils.mojang_api import VALID_MINECRAFT_VERSIONS, fetch_mojang_versions

# Config follows the documentation at: https://docker-minecraft-server.readthedocs.io/en/latest/variables/
class MinecraftServerConfig(BaseModel, ABC):
    memory_limit: int = Field(..., ge=1)
    cpu_cores_limit: float = Field(..., gt=0.0)
    eula: bool = Field(...)
    version: str = Field(...)
    type: str = Field(...)
    motd: str = Field(default="Brought to you by Divum. Enjoy!")
    difficulty: str = Field(default="easy")
    mode: str = Field(default="survival")
    level: str = Field(default="world")
    online_mode: bool = Field(default=True)

    resource_pack: str = Field(default="")
    resource_pack_sha1: str = Field(default="")
    resource_pack_enforce: bool = Field(default=False)

    enable_whitelist: bool = Field(default=False)
    whitelist: list[str] = Field(default=[])
    override_whitelist: bool = Field(default=False)

    enable_rcon: bool = Field(default=True)
    rcon_password: str = Field(...)
    broadcast_rcon_to_ops: bool = Field(default=False)

    ops: list[str] = Field(default=[])
    op_permission_level: int = Field(default=0, ge=0, le=4)

    seed: str = Field(default="")
    pvp: bool = Field(default=True)
    server_name: str = Field(...)

    server_address: str = Field(...)

    @abstractmethod
    def export(self) -> dict[str, str]:
        """Converts the config into a dictionary"""

        env = {
            "MEMORY": f"{self.memory_limit}M",
            "TYPE": self.type.upper(),
            "EULA": "TRUE" if self.eula else "FALSE",
            "VERSION": self.version,
            "MOTD": self.motd,
            "DIFFICULTY": self.difficulty,
            "MODE": self.mode,
            "LEVEL": self.level,
            "ONLINE_MODE": "TRUE" if self.online_mode else "FALSE",

            "RESOURCE_PACK": self.resource_pack,
            "RESOURCE_PACK_SHA1": self.resource_pack_sha1,
            "RESOURCE_PACK_ENFORCE": "TRUE" if self.resource_pack_enforce else "FALSE",

            "ENABLE_RCON": "TRUE" if self.enable_rcon else "FALSE",
            "RCON_PASSWORD": self.rcon_password,
            "BROADCAST_RCON_TO_OPS": "TRUE" if self.broadcast_rcon_to_ops else "FALSE",

            "OVERRIDE_WHITELIST": "TRUE" if self.override_whitelist else "FALSE",

            "PVP": "TRUE" if self.pvp else "FALSE",
            "SERVER_NAME": self.server_name,
        }

        if self.enable_whitelist and self.whitelist:
            env["WHITELIST"] = ','.join(self.whitelist)
            env["ENABLE_WHITELIST"] = "TRUE"

        if self.seed:
            env["SEED"] = self.seed

        return env

    @field_validator("memory_limit")
    @classmethod
    def validate_memory_limit(cls, v: int) -> int:
        # Gets the total system memory in MB
        # There are alternatives to the .total field that can be used
        system_memory: int = int(psutil.virtual_memory().total / (1024 * 1024))
        if v > system_memory:
            # TODO: need to leave resources for the system itself ??
            raise ValueError("Can't satisfy given memory")

        return v


    @field_validator("cpu_cores_limit")
    @classmethod
    def validate_cpu_cores_limit(cls, v: float) -> float:
        system_cpu_count: int | None = os.cpu_count()
        if system_cpu_count is None and v > 8:
            # TODO: MUST BE LOGGED
            raise ValueError("Can't satisfy given CPU cores")
        if system_cpu_count is not None and v > system_cpu_count:
            # TODO: need to leave resources for the system itself ??
            raise ValueError("Can't satisfy given CPU cores")

        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        if v.upper() in {"LATEST", "SNAPSHOT"}:
            return v

        if v in VALID_MINECRAFT_VERSIONS:
            return v

        # Update cache if version hasn't been seen
        fetch_mojang_versions()

        if v in VALID_MINECRAFT_VERSIONS:
            return v

        raise ValueError(f"Minecraft version '{v}' is not recognized by Mojang.")

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        difficulty_levels: set[str] = {"peaceful", "easy", "normal", "hard"}

        if v.lower() not in difficulty_levels:
            raise ValueError(f"Difficulty level {v} is not supported.")

        return v.lower()

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        mode_types: set[str] = {"creative", "survival", "adventure", "spectator"}

        if v.lower() not in mode_types:
            raise ValueError(f"Server mode {v} is not supported.")

        return v.lower()

    @field_validator("server_name")
    @classmethod
    def validate_server_name(cls, v: str):
        if ":" in v:
            raise ValueError(f"Server name cannot contain ':'")

        return v

    @field_validator("server_address")
    @classmethod
    def validate_server_address(cls, v: str):
        # Basic regex for standard domain structures
        # 1. Allows alphanumeric characters and hyphens
        # 2. Ensures no hyphen at the start or end of a segment
        # 3. Ensures at least one dot
        # 4. TLD must be at least 2 characters
        pattern = r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})+$"

        if not re.match(pattern, v):
            raise ValueError("Invalid domain.")
        return v

