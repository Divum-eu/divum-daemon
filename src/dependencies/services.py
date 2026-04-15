from services.docker_server_manager import DockerServerManager
from services.server_manager import ServerManager


_docker_server_manager: DockerServerManager = DockerServerManager()


def get_docker_server_manager() -> ServerManager:
    return _docker_server_manager
