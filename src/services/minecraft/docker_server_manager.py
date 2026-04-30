"""
Contains the main service responsible for handling Minecraft server container instances.
"""
from typing import AnyStr

from exceptions.create_container_exception import CreateContainerException

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
    HOT_UPDATE_KEYS = {"DIFFICULTY", "MODE"}

    def __init__(self, proxy_router: ProxyRouter):
        try:
            self._client = docker.from_env()
            self._proxy_router: ProxyRouter = proxy_router
        except Exception as err:
            raise ClientAPIException("Couldn't start the Docker client.") from err

    async def create(self, config: MinecraftServerConfig) -> str | None:
        """Creates an itzg/minecraft-server container with the given configuration"""
        try:
            # await asyncio.to_thread(
            #     self._client.images.pull, MINECRAFT_SERVER_DOCKER_IMAGE, tag="latest"
            # )

            container_name: str = str(uuid.uuid4())

            host_path = os.path.abspath(f"{WORLDS_DIR}/data/{container_name}")
            os.makedirs(host_path)

            container: Container | None = await self._create_container(container_name, config, host_path)

            if not container:
                print("No container")
                return None

        except ImageNotFound as ex:
            raise DockerImageNotFoundException(MINECRAFT_SERVER_DOCKER_IMAGE) from ex
        except APIError as err:
            raise ClientAPIException(
                f"An error occurred while trying to create a container from image '{MINECRAFT_SERVER_DOCKER_IMAGE}'."
            ) from err

        # Maps to the internal port since mc-router and the server container run on the same docker network
        if not await self._proxy_router.add(config.server_address, f"{container_name}:{self.MC_CONTAINER_PORT}"):
            await self._remove(container_name, permanently=True, force=True) # TODO: implement internal codes
            return None

        await self.start(container.name)
        return container.name

    async def update(self, server_id: str, new_config: MinecraftServerConfig) -> bool:
        print("In update")
        container: Container | None = await self._get_container(server_id)
        if not container:
            # TODO: log
            raise DockerContainerNotFoundException(server_id)

        was_running: bool = container.status == Status.RUNNING

        current_env = {}
        for env_str in container.attrs["Config"]["Env"]:
            if "=" in env_str:
                k, v = env_str.split("=", 1)
                current_env[k] = v

        new_env = new_config.export()

        changed_keys = [k for k, v in new_env.items() if current_env.get(k) != v]

        requires_restart = any(key not in self.HOT_UPDATE_KEYS for key in changed_keys)

        pending_path = os.path.abspath(f"{WORLDS_DIR}/data/{server_id}/.pending_config.json")
        if requires_restart or not was_running:
            print("In requires restart or not was_running")
            pending_path = os.path.abspath(f"{WORLDS_DIR}/data/{server_id}/.pending_config.json")
            if os.path.exists(pending_path):
                os.remove(pending_path)

            return await self._recreate_container(server_id, new_config, was_running)

        await self._apply_live_patches(server_id, new_config)
        with open(pending_path, "w") as f:
            f.write(new_config.model_dump_json())

        return True


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
        print("Start container")
        try:
            container: Container | None = await self._get_container(server_id)

            if not container:
                raise DockerContainerNotFoundException

            await asyncio.to_thread(container.start)

        except (NotFound, APIError):
            return False

        return True

    async def stop(self, server_id: str) -> bool:
        try:
            container: Container | None = await self._get_container(server_id)

            if not container:
                return False

            await asyncio.to_thread(container.stop)

        except (NotFound, APIError):
            return False

        return True

    async def delete(self, server_id: str) -> bool:
        return await self._remove(server_id, True, True)

    async def _remove(self, server_id: str, permanently: bool, force: bool) -> bool:
        try:
            container: Container = await asyncio.to_thread(
                self._client.containers.get, server_id
            )

            await asyncio.to_thread(container.remove, v=permanently, force=force)
            await self._proxy_router.remove(f"{container.name}")

        except (NotFound, APIError):
            return False

        return True

    async def _get_container(self, server_id: str) -> Container | None:
        try:
            container: Container = await asyncio.to_thread(
                self._client.containers.get, server_id
            )
            return container
        except (NotFound, APIError):
            return None

    async def _recreate_container(self, server_id: str, new_config: MinecraftServerConfig, was_running: bool) -> bool:
        print("In recreate container")
        await self.stop(server_id)
        await self._remove(server_id, permanently=False, force=True)

        if not new_config.online_mode and new_config.whitelist and new_config.enable_whitelist:
            new_config.whitelist = [self.generate_offline_uuid(u) for u in new_config.whitelist]

        host_path = os.path.abspath(f"{WORLDS_DIR}/data/{server_id}")

        new_container: Container | None = await self._create_container(server_id, new_config, host_path)
        if not new_container:
            raise CreateContainerException

        await self._proxy_router.add(new_config.server_address, f"{new_container.name}:{self.MC_CONTAINER_PORT}")

        if was_running:
            await self.start(server_id)

        return True

    async def _create_container(self, server_id: str, config: MinecraftServerConfig, host_path: AnyStr) -> Container | None:
        print("in create container")
        try:
            print(config.export())
            new_container: Container = await asyncio.to_thread(
                self._client.containers.create,
                MINECRAFT_SERVER_DOCKER_IMAGE,
                name=server_id,
                environment=config.export(),
                nano_cpus=int(config.cpu_cores_limit * (10 ** 9)),
                volumes={host_path: {"bind": "/data", "mode": "rw,Z"}},
                dns=["8.8.8.8", "1.1.1.1"],
                network=DOCKER_NETWORK_NAME,
                labels={
                    # Needed for itzg/mc-router to be able to see the container and automatically scale it
                    "mc-router.host": config.server_address
                },
                detach=True,
            )
            return new_container
        except ImageNotFound:
            try:
                print("pulling image")
                await asyncio.to_thread(self._client.images.pull,
                                        MINECRAFT_SERVER_DOCKER_IMAGE,
                                        tag="latest"
                                        )

                print("image pulled")
                return await self._create_container(server_id, config, host_path)
            except APIError:
                return None

        except APIError as err:
            return None

    async def _apply_live_patches(self, server_id: str, new_config: MinecraftServerConfig) -> bool:
        container: Container | None = await asyncio.to_thread(
            self._client.containers.get, server_id
        )
        print(new_config.export())

        json_config = new_config.export()

        async def run_rcon(command: str):
            await asyncio.to_thread(container.exec_run, f"rcon-cli {command.lower()}")

        if "DIFFICULTY" in json_config:
            await run_rcon(f"difficulty {new_config.difficulty}")

        if "MODE" in json_config:
            await run_rcon(f"defaultgamemode {new_config.mode}")
            await run_rcon(f"gamemode {new_config.mode} @a")

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
