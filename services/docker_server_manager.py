import os
import shutil

import docker
from docker.models.containers import Container
from dotenv import load_dotenv

from exceptions.client_api_exception import ClientAPIException
from exceptions.docker_container_not_found_exception import DockerContainerNotFoundException
from exceptions.docker_image_not_found_exception import DockerImageNotFoundException
from exceptions.server_name_already_exists_exception import ServerNameAlreadyExistsException
from schemas.minecraft_server_config import MinecraftServerConfig
from schemas.minecraft_server_status import MinecraftServerStatus, Status
from server_manager import ServerManager

load_dotenv()
DOCKER_MINECRAFT_IMAGE = "itzg/minecraft-server"
WORLDS_DIR = os.environ.get("WORLDS_DIR", "..")

# TODO: add logging
class DockerServerManager(ServerManager):
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as err:
            raise ClientAPIException(str(err))

    def create(self, config: MinecraftServerConfig ) -> str | None:
        try:
            if self.__exists(config.server_name):
                raise ServerNameAlreadyExistsException(config.server_name)

            self.client.images.pull("itzg/minecraft-server", tag="latest")

            host_path = os.path.abspath(f"{WORLDS_DIR}/data/{config.server_name}")
            if not os.path.exists(host_path):
                os.makedirs(host_path)
            else:
                shutil.rmtree(host_path)
                os.makedirs(host_path)

            container = self.client.containers.create(
                DOCKER_MINECRAFT_IMAGE,
                name=f"{config.server_name}",
                environment=config.to_docker_env(),
                nano_cpus=int(config.cpu_cores * (10 ** 9)), # 1 core = 10 ^ 9
                volumes={
                    host_path: {
                        "bind": "/data",
                        "mode": "rw,Z"
                    }
                },
                ports={
                    '25565/tcp': 25565,  # Minecraft Game Port
                    '25575/tcp': 25575  # RCON Port
                },
                detach=True,
            )

        except docker.errors.ImageNotFound:
            raise DockerImageNotFoundException(DOCKER_MINECRAFT_IMAGE)
        except docker.errors.APIError as err:
            raise ClientAPIException(err)

        return container.name

    def status(self, server_id: str) -> MinecraftServerStatus:
        try:
            container: Container = self.client.containers.get(server_id)

            status = container.status
            log = "No logs"

            # If the minecraft instance was very recently created, log files are not yet generated
            host_path = os.path.abspath(f"{WORLDS_DIR}/data/{container.name}/logs/latest.log")
            if os.path.exists(host_path):
                with open(host_path, "r") as log_file:
                    log = log_file.read()

            return MinecraftServerStatus(status=Status(value=status), log=log)

        except docker.errors.NotFound:
            raise DockerContainerNotFoundException(server_id)
        except docker.errors.APIError as err:
            raise ClientAPIException(err)

    def start(self, server_id: str) -> bool:
        try:
            self.client.containers.get(server_id).start()
        except docker.errors.NotFound:
            return False
        except docker.errors.APIError as err:
            return False

        return True

    def stop(self, server_id: str) -> bool:
        try:
            self.client.containers.get(server_id).stop()
        except docker.errors.NotFound:
            return False
        except docker.errors.APIError as err:
            return False

        return True

    def __exists(self, server_name: str) -> bool:
        try:
            self.client.containers.get(server_name)
            return True
        except docker.errors.NotFound:
            return False
        except docker.errors.APIError as err:
            raise ClientAPIException(str(err))


manager = DockerServerManager()

config: MinecraftServerConfig = MinecraftServerConfig(
    server_name="dimpex",
    memory=2,
    cpu_cores=1,
    type="FABRIC",
    eula=True,
    difficulty="hard",
    mode="creative",
    level="swqt",
    resource_pack="https://download.mc-packs.net/pack/59eb5f3c13e5a064dae879cce3e4c6aff6bf9b87.zip",
    resource_pack_sha1="59eb5f3c13e5a064dae879cce3e4c6aff6bf9b87",
    online_mode=False,
)

manager.create(config)
manager.start(config.server_name)
# manager.stop(config.server_name)
status: MinecraftServerStatus = manager.status(config.server_name)
print(status.status.name)
print(status.log)