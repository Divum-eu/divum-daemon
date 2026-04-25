from abc import ABC, abstractmethod


class ProxyRouter(ABC):

    @abstractmethod
    async def add(self, server_address: str, server_host: str) -> bool:
        """Add an entry"""
        pass

    @abstractmethod
    async def remove(self, server_address: str) -> bool:
        """Remove an entry"""
        pass