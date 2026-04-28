"""
Contains the main service responsible for handling Minecraft server container instances.
"""

import asyncio

import hashlib

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

from services.minecraft.proxy_router import ProxyRouter
from services.minecraft.server_manager import ServerManager

from schemas.minecraft_server_status import MinecraftServerStatus, Status
from schemas.minecraft_server_config.minecraft_server_config import MinecraftServerConfig


WORLDS_DIR = os.environ.get("WORLDS_DIR", "../..")
DOCKER_NETWORK_NAME = os.environ.get("DOCKER_NETWORK_NAME", "divum-net")


# TODO: add logging
class DockerServerManager(ServerManager):
    """
    The service responsible for handling Minecraft server container instances.
    """

    MC_CONTAINER_PORT: int = 25565

    def __init__(self, proxy_router: ProxyRouter):
        try:
            self._client = docker.from_env()
            self._proxy_router: ProxyRouter = proxy_router
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

            # If online mode is disabled and the user wants whitelist functionality, generate offline UUIDs
            if not config.online_mode and config.whitelist and config.enable_whitelist:
                new_whitelist: list[str] = []
                for username in config.whitelist:
                    new_whitelist.append(self.generate_offline_uuid(username))
                config.whitelist = new_whitelist


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
                # Bypasses Docker's unstable internal DNS proxy to prevent
                # UnknownHostExceptions when downloading server.jar or hitting Mojang APIs
                dns=["8.8.8.8", "1.1.1.1"],
                network=DOCKER_NETWORK_NAME,
                detach=True,
            )

        except ImageNotFound as ex:
            raise DockerImageNotFoundException(MINECRAFT_SERVER_DOCKER_IMAGE) from ex
        except APIError as err:
            raise ClientAPIException(
                f"An error occurred while trying to create a container from image '{MINECRAFT_SERVER_DOCKER_IMAGE}'."
            ) from err

        # Maps to the internal port since mc-router and the server container run on the same docker network
        if not await self._proxy_router.add(config.server_address, f"{container_name}:{self.MC_CONTAINER_PORT}"):
            await self.remove(container_name) # TODO: implement internal codes
            return None

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
                f"An error occurred while trying to get the status of container '{server_id}'."
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

    async def remove(self, server_id: str) -> bool:
        try:
            container: Container = await asyncio.to_thread(
                self._client.containers.get, server_id
            )

            await asyncio.to_thread(container.remove, v=True, force=True)
            await self._proxy_router.remove(f"{container.name}:{self.MC_CONTAINER_PORT}")

        except (NotFound, APIError):
            return False

        return True

    @staticmethod
    def generate_offline_uuid(username: str) -> str:
        # 1. Create the string
        data = f"OfflinePlayer:{username}".encode('utf-8')

        # 2. Get the MD5 hash
        md5_hash = hashlib.md5(data).digest()

        # 3. Apply the UUID version 3 and variant bits
        # (Setting the 7th byte for version 3, and 9th byte for variant 2)
        uuid_bytes = bytearray(md5_hash)
        uuid_bytes[6] = (uuid_bytes[6] & 0x0f) | 0x30  # remove first 4 bits and replace with the number 3 (0x30)
        uuid_bytes[8] = (uuid_bytes[8] & 0x3f) | 0x80  # remove first 2 bits and replace with the number 8 (0x80)

        # 4. Return as a formatted UUID object/string
        return str(uuid.UUID(bytes=bytes(uuid_bytes)))
