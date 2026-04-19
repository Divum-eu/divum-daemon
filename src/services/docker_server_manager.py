import os
import uuid

import docker
from docker.models.containers import Container

from dotenv import load_dotenv

from exceptions.docker_container_not_found_exception import DockerContainerNotFoundException
from schemas.minecraft_server_config.minecraft_fabric_server_config import MinecraftFabricServerConfig
from schemas.minecraft_server_config.minecraft_vanilla_server_config import MinecraftVanillaServerConfig

from src.exceptions.client_api_exception import ClientAPIException
from src.exceptions.docker_image_not_found_exception import DockerImageNotFoundException

from src.services.server_manager import ServerManager

from src.schemas.minecraft_server_status import MinecraftServerStatus, Status

from schemas.minecraft_server_config.minecraft_server_config import MinecraftServerConfig

load_dotenv()

DOCKER_MINECRAFT_IMAGE = "itzg/minecraft-server"
WORLDS_DIR = os.environ.get("WORLDS_DIR", "..")

# TODO: add logging
class DockerServerManager(ServerManager):
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as err:
            print(err)
            raise ClientAPIException(str(err))

    def create(self, config: MinecraftServerConfig) -> str | None:
        """Creates an itzg/minecraft-server container with the given configuration"""
        try:
            self.client.images.pull("itzg/minecraft-server", tag="latest")

            container_name: str = str(uuid.uuid4())

            host_path = os.path.abspath(f"{WORLDS_DIR}/data/{container_name}")
            os.makedirs(host_path)

            container = self.client.containers.create(
                DOCKER_MINECRAFT_IMAGE,
                name=container_name,
                environment=config.export(),
                nano_cpus=int(config.cpu_cores_limit * (10 ** 9)), # 1 core = 10 ^ 9
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
                # Bypasses Docker's unstable internal DNS proxy to prevent
                # UnknownHostExceptions when downloading server.jar or hitting Mojang APIs
                dns=["8.8.8.8", "1.1.1.1"],
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


# FOR TESTING

# manager = DockerServerManager()
#
# config: MinecraftServerConfig = MinecraftFabricServerConfig(
#     memory_limit=2048,
#     cpu_cores_limit=1,
#     server_name="dimpex",
#     type="FABRIC",
#     eula=True,
#     difficulty="hard",
#     mode="creative",
#     level="swqt",
#     resource_pack="https://download.mc-packs.net/pack/59eb5f3c13e5a064dae879cce3e4c6aff6bf9b87.zip",
#     resource_pack_sha1="59eb5f3c13e5a064dae879cce3e4c6aff6bf9b87",
#     online_mode=False,
#     enable_whitelist=True,
#     whitelist=["Dimpex", "Dimitar45"],
#     rcon_password="123",
#     version="latest"
# )
#
# name: str | None = manager.create(config)
# manager.start(name)
# # manager.stop(config.server_name)
# status: MinecraftServerStatus = manager.status(name)
# print(status.status.name)
# print(status.log)