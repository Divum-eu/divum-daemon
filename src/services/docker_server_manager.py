import docker

from src.exceptions.client_api_exception import ClientAPIException
from src.exceptions.docker_image_not_found_exception import DockerImageNotFoundException
from src.exceptions.server_name_already_exists_exception import ServerNameAlreadyExistsException
from src.services.server_manager import ServerManager

DOCKER_MINECRAFT_IMAGE = "itzg/minecraft-server"

# TODO: add logging
class DockerServerManager(ServerManager):
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as err:
            raise ClientAPIException(str(err))

    def create_server(self, server_name: str) -> str | None:
        try:
            if self.__server_exists(server_name):
                raise ServerNameAlreadyExistsException(server_name)

            self.client.images.pull("itzg/minecraft-server", tag="latest")

            container = self.client.containers.create(
                DOCKER_MINECRAFT_IMAGE,
                name=f"{server_name}",
                environment={"EULA": "TRUE", "MEMORY": f"{4}G"}, # TODO: memory must come from config param
                detach=True,
                nano_cpus=1 * (10 ** 9), # TODO: cpu must come from config param
            )
            # TODO: mount volume for persistent worlds

        except docker.errors.ImageNotFound:
            raise DockerImageNotFoundException(DOCKER_MINECRAFT_IMAGE)
        except docker.errors.APIError as err:
            raise ClientAPIException(err)

        return container.name

    def start_server(self, server_id: str) -> bool:
        try:
            self.client.containers.get(server_id).start()
        except docker.errors.APIError:
            return False

        return True

    def stop_server(self, server_id: str) -> bool:
        try:
            self.client.containers.get(server_id).stop()
        except docker.errors.APIError:
            return False

        return True

    def __server_exists(self, server_name: str) -> bool:
        return self.client.containers.list(all=True, filters={"name": server_name})