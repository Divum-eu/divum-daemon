from abc import ABC, abstractmethod

from schemas.minecraft_server_itzg_config import MinecraftServerITZGConfig


class ServerManager(ABC):

    @abstractmethod
    def create(self, config: MinecraftServerITZGConfig) -> str | None:
        """Creates a server and return the unique identifier for it"""
        pass

    @abstractmethod
    def status(self, server_id: str) -> str:
        """"""
        pass

    @abstractmethod
    def start(self, server_id: str) -> bool:
        """Starts an existing server"""
        pass

    @abstractmethod
    def stop(self, server_id: str) -> bool:
        """Stops an existing server"""
        pass