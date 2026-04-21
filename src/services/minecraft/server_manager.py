from abc import ABC, abstractmethod

from schemas.minecraft_server_status import MinecraftServerStatus
from schemas.minecraft_server_config.minecraft_server_config import MinecraftServerConfig

class ServerManager(ABC):
    @abstractmethod
    async def create(
        self, config: MinecraftServerConfig
    ) -> str | None:
        """Creates a server and return the unique identifier for it"""
        pass

    @abstractmethod
    async def status(self, server_id: str) -> MinecraftServerStatus:
        """Returns the status of an existing instance and its logs"""
        pass

    @abstractmethod
    async def start(self, server_id: str) -> bool:
        """Starts an existing server"""
        pass

    @abstractmethod
    async def stop(self, server_id: str) -> bool:
        """Stops an existing server"""
        pass

    @abstractmethod
    async def remove(self, server_id: str) -> bool:
        """Removes an existing server"""
        pass
