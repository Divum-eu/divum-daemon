from typing import Optional

from fastapi import Depends

from services.minecraft.docker_server_manager import DockerServerManager
from services.minecraft.mc_proxy_router import MCProxyRouter
from services.minecraft.proxy_router import ProxyRouter
from services.minecraft.server_manager import ServerManager


# Global holders for the singleton instances
_proxy_router_instance: Optional[ProxyRouter] = None
_server_manager_instance: Optional[ServerManager] = None

def get_mc_proxy_router() -> ProxyRouter:
    """Provides a singleton instance of ProxyRouter."""
    global _proxy_router_instance
    if _proxy_router_instance is None:
        # Instantiation happens only on first request/call
        _proxy_router_instance = MCProxyRouter()
    return _proxy_router_instance

def get_docker_server_manager(
    router: ProxyRouter = Depends(get_mc_proxy_router)
) -> ServerManager:
    """Provides a singleton instance of ServerManager, managed by DI."""
    global _server_manager_instance
    if _server_manager_instance is None:
        # We use the 'router' provided by the DI container
        _server_manager_instance = DockerServerManager(router)
    return _server_manager_instance
