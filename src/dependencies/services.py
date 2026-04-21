from services.minecraft.docker_server_manager import DockerServerManager
from services.minecraft.mc_proxy_router import MCProxyRouter
from services.minecraft.proxy_router import ProxyRouter
from services.minecraft.server_manager import ServerManager


_mc_proxy_router: ProxyRouter = MCProxyRouter()

def get_mc_proxy_router() -> ProxyRouter:
    return _mc_proxy_router


_docker_server_manager: ServerManager = DockerServerManager(get_mc_proxy_router())

def get_docker_server_manager() -> ServerManager:
    return _docker_server_manager
