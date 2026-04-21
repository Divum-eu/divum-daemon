"""
Contains the main service responsible for handling Minecraft server container instances.
"""

import asyncio

import os

import uuid

import docker
from docker.models.containers import Container
from docker.errors import APIError, ImageNotFound, NotFound

from constants.constants import MINECRAFT_SERVER_DOCKER_IMAGE

from exceptions.client_api_exception import ClientAPIException
from exceptions.docker_container_not_found_exception import (
    DockerContainerNotFoundException,
)
from exceptions.docker_image_not_found_exception import DockerImageNotFoundException

from services.server_manager import ServerManager

from schemas.minecraft_server_status import MinecraftServerStatus, Status

from schemas.minecraft_server_config.minecraft_server_config import MinecraftServerConfig

WORLDS_DIR = os.environ.get("WORLDS_DIR", "..")


# TODO: add logging
class DockerServerManager(ServerManager):
    """
    The service responsible for handling Minecraft server container instances.
    """

    def __init__(self):
        try:
            self._client = docker.from_env()
        except Exception as err:
            raise ClientAPIException("Couldn't start the Docker client.") from err

    async def create(self, config: MinecraftServerConfig) -> str | None:
        """Creates an itzg/minecraft-server container with the given configuration"""
        try:
            await asyncio.to_thread(
                self._client.images.pull, MINECRAFT_SERVER_DOCKER_IMAGE, tag="latest"
            )

            container_name: str = str(uuid.uuid4())

            host_path = os.path.abspath(f"{WORLDS_DIR}/data/{container_name}")
            os.makedirs(host_path)

            container: Container = await asyncio.to_thread(
                self._client.containers.create,
                MINECRAFT_SERVER_DOCKER_IMAGE,
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
                    "25565/tcp": 25565,  # Minecraft Game Port
                    "25575/tcp": 25575,  # RCON Port
                },
                # Bypasses Docker's unstable internal DNS proxy to prevent
                # UnknownHostExceptions when downloading server.jar or hitting Mojang APIs
                dns=["8.8.8.8", "1.1.1.1"],
                detach=True,
            )

        except ImageNotFound as ex:
            raise DockerImageNotFoundException(MINECRAFT_SERVER_DOCKER_IMAGE) from ex
        except APIError as err:
            raise ClientAPIException(
                f"An error occurred while trying to create a container from image '{MINECRAFT_SERVER_DOCKER_IMAGE}'."
            ) from err

        return container.name

    async def status(self, server_id: str) -> MinecraftServerStatus:
        try:
            container: Container = await asyncio.to_thread(
                self._client.containers.get, server_id
            )

            status = container.status
            log = "No logs"

            # If the minecraft instance was very recently created, log files are not yet generated
            host_path = os.path.abspath(
                f"{WORLDS_DIR}/data/{container.name}/logs/latest.log"
            )
            if os.path.exists(host_path):
                with open(host_path, "r") as log_file:
                    log = log_file.read()

            return MinecraftServerStatus(status=Status(value=status), log=log)

        except NotFound as ex:
            raise DockerContainerNotFoundException(server_id) from ex
        except APIError as err:
            raise ClientAPIException(
                f"An error occurred while trying get the status of container '{server_id}'."
            ) from err

    async def start(self, server_id: str) -> bool:
        try:
            container: Container = await asyncio.to_thread(
                self._client.containers.get, server_id
            )

            await asyncio.to_thread(container.start)

        except (NotFound, APIError):
            return False

        return True

    async def stop(self, server_id: str) -> bool:
        try:
            container: Container = await asyncio.to_thread(
                self._client.containers.get, server_id
            )

            await asyncio.to_thread(container.stop)

        except (NotFound, APIError):
            return False

        return True

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
