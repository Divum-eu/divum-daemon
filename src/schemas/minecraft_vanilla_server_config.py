from abc import ABC
from typing import Literal

from schemas.minecraft_server_config import MinecraftServerConfig


class MinecraftVanillaServerConfig(MinecraftServerConfig, ABC):
    type: Literal["VANILLA"] = "VANILLA"

    def export(self) -> dict[str, str]:
        return super().export()