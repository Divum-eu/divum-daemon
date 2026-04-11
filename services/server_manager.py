from abc import ABC, abstractmethod

class ServerManager(ABC):

    @abstractmethod
    def create_server(self, server_name: str) -> str | None: # TODO: add a configuration param: custom type
        """Creates a server and return the unique identifier for it"""
        pass

    def start_server(self, server_id: str) -> bool:
        """Starts an existing server"""
        pass

    def stop_server(self, server_id: str) -> bool:
        """Stops an existing server"""
        pass