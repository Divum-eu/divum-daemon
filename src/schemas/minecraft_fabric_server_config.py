from abc import ABC
from typing import Literal

from pydantic import Field

from schemas.minecraft_server_config import MinecraftServerConfig


class MinecraftFabricServerConfig(MinecraftServerConfig, ABC):
    type: Literal["FABRIC"] = "FABRIC"

    fabric_launcher_version: str = Field(default="LATEST")
    fabric_loader_version: str = Field(default="LATEST")

    def export(self) -> dict[str, str]:
        env: dict[str, str] = super().export()

        if self.fabric_launcher_version != "LATEST":
            env["FABRIC_LAUNCHER_VERSION"] = self.fabric_launcher_version
        if self.fabric_loader_version != "LATEST":
            env["FABRIC_LOADER_VERSION"] = self.fabric_loader_version

        return env