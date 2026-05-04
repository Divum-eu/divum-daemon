"""
Contains the main service responsible for handling Minecraft server container instances.
"""
import json
from typing import AnyStr

import aiofiles
import aiohttp
from aiohttp import ClientConnectionError

from exceptions.create_container_exception import CreateContainerException

import asyncio

import hashlib

import os

import uuid

import docker
from docker.models.containers import Container
from docker.errors import APIError, ImageNotFound, NotFound

from constants.constants import MINECRAFT_SERVER_DOCKER_IMAGE, DOCKER_CONTAINER_CPU_MULTIPLIER, \
    MC_ROUTER_CONTAINER_LABEL

from exceptions.client_api_exception import ClientAPIException
from exceptions.docker_container_not_found_exception import DockerContainerNotFoundException

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
    HOT_UPDATE_KEYS = {"DIFFICULTY", "MODE", "WHITELIST"}

    def __init__(self, proxy_router: ProxyRouter):
        try:
            self._client = docker.from_env()
        except Exception as err:
            raise ClientAPIException("Couldn't start the Docker client.") from err


    async def create(self, config: MinecraftServerConfig) -> str | None:
        """Creates an itzg/minecraft-server container with the given configuration"""

        # Generate name and create a folder on the host to mount to the container
        container_name: str = str(uuid.uuid4())

        host_path = os.path.abspath(f"{WORLDS_DIR}/data/{container_name}")
        os.makedirs(host_path)

        container: Container | None = await self._create_container(container_name, config, host_path)

        # remove the created the folder if creation failed
        if not container:
            if os.path.exists(host_path):
                os.rmdir(host_path)
            return None

        await self.start(container_name)
        return container.name


    async def update(self, server_id: str, new_config: MinecraftServerConfig) -> bool:
        container: Container | None = await self._get_container(server_id)
        if not container:
            # TODO: log
            raise DockerContainerNotFoundException(server_id)

        was_running: bool = container.status == Status.RUNNING

        # Extract all variables from the container
        current_env = {}
        for env_str in container.attrs["Config"]["Env"]:
            if "=" in env_str:
                k, v = env_str.split("=", 1)
                current_env[k] = v

        new_env = new_config.export()

        changed_keys = [k for k, v in new_env.items() if current_env.get(k) != v]

        # Checks if the server address has been changed
        current_address: str = container.labels.get(MC_ROUTER_CONTAINER_LABEL)
        new_address: str = new_config.server_address
        server_address_changed: bool = current_address != new_address

        # Checks if the cpu limit has been changed
        cpu_limit_changed: bool = (
                new_config.cpu_cores_limit * DOCKER_CONTAINER_CPU_MULTIPLIER != container.attrs["HostConfig"].get("NanoCpus")
        )

        requires_restart: bool = (any(key not in self.HOT_UPDATE_KEYS for key in changed_keys)
                            or cpu_limit_changed
                            or server_address_changed)

        pending_path = os.path.abspath(f"{WORLDS_DIR}/data/{server_id}/.pending_config.json")
        if requires_restart or not was_running:
            pending_path = os.path.abspath(f"{WORLDS_DIR}/data/{server_id}/.pending_config.json")
            if os.path.exists(pending_path):
                os.remove(pending_path)

            online_mode_changed: bool = current_env["ONLINE_MODE"] != new_config.online_mode
            return await self._recreate_container(server_id, new_config, online_mode_changed, was_running)

        # Generate a .pending_config.json file to be applied on server stop
        await self._apply_live_patches(server_id, new_config)
        async with aiofiles.open(pending_path, "w") as f:
            await f.write(new_config.model_dump_json())

        return True

    # TODO: remove-ni go toq bokluk che samo me drazni
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
        return await self._remove(server_id, permanently=True, force=True)


    async def _remove(self, server_id: str, permanently: bool, force: bool) -> bool:
        try:
            container: Container = await asyncio.to_thread(
                self._client.containers.get, server_id
            )

            await asyncio.to_thread(container.remove, v=permanently, force=force)
            if permanently:
                host_path = os.path.abspath(f"{WORLDS_DIR}/data/{server_id}")
                if os.path.exists(host_path):
                    os.rmdir(host_path)

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

    async def _recreate_container(self, server_id: str, new_config: MinecraftServerConfig, online_mode_changed: bool, was_running: bool) -> bool:
        await self.stop(server_id)
        await self._remove(server_id, permanently=False, force=True)

        if online_mode_changed:
            await self._migrate_all_players(server_id, new_config.online_mode)

            poisoned_files = ["usercache.json", "whitelist.json", "ops.json", "banned-players.json"]
            for file_name in poisoned_files:
                file_path = os.path.join(f"{WORLDS_DIR}/data/{server_id}", file_name)
                if os.path.exists(file_path):
                    os.remove(file_path)

        host_path = os.path.abspath(f"{WORLDS_DIR}/data/{server_id}")

        new_container: Container | None = await self._create_container(server_id, new_config, host_path)
        if not new_container:
            raise CreateContainerException

        if was_running:
            await self.start(server_id)

        return True

    async def _create_container(self, server_id: str, config: MinecraftServerConfig, host_path: AnyStr) -> Container | None:
        try:
            if not config.online_mode and config.whitelist and config.enable_whitelist:
                config.whitelist = [self.generate_offline_uuid(username) for username in config.whitelist]

            new_container: Container = await asyncio.to_thread(
                self._client.containers.create,
                MINECRAFT_SERVER_DOCKER_IMAGE,
                name=server_id,
                environment=config.export(),
                nano_cpus=int(config.cpu_cores_limit * DOCKER_CONTAINER_CPU_MULTIPLIER),
                volumes={host_path: {"bind": "/data", "mode": "rw,Z"}},
                dns=["8.8.8.8", "1.1.1.1"],
                network=DOCKER_NETWORK_NAME,
                labels={
                    # Needed for itzg/mc-router to be able to see the container and automatically scale it
                    MC_ROUTER_CONTAINER_LABEL: config.server_address,
                },
                detach=True,
            )
            return new_container
        except ImageNotFound:
            try:
                # Try to pull the image and retry the creation. In theory, it shouldn't go in an infinite recursion
                if await self._pull_image(MINECRAFT_SERVER_DOCKER_IMAGE):
                    return await self._create_container(server_id, config, host_path)
            except APIError:
                return None

        except APIError:
            return None

    async def _pull_image(self, image: str) -> bool:
        try:
            await asyncio.to_thread(self._client.images.pull,
                                repository=image,
                                tag="latest"
                                )
        except APIError:
            return False

        return True


    async def _apply_live_patches(self, server_id: str, new_config: MinecraftServerConfig) -> bool:
        container: Container | None = await asyncio.to_thread(
            self._client.containers.get, server_id
        )
        if not container:
            return False

        json_config = new_config.export()

        async def run_rcon(command: str):
            await asyncio.to_thread(container.exec_run, f"rcon-cli {command}")

        if "DIFFICULTY" in json_config:
            await run_rcon(f"difficulty {new_config.difficulty}")

        if "MODE" in json_config:
            await run_rcon(f"defaultgamemode {new_config.mode}")
            await run_rcon(f"gamemode {new_config.mode} @a")

        if "WHITELIST" in json_config:
            # Enforce the whitelist
            if new_config.enable_whitelist:
                await run_rcon("whitelist on")
            else:
                await run_rcon("whitelist off")

            # Build the JSON data
            whitelist_data = []
            if new_config.whitelist:
                for name in new_config.whitelist:
                    if new_config.online_mode:
                        player_uuid = await self.get_premium_uuid(name)
                    else:
                        player_uuid = self.generate_offline_uuid(name)

                    if player_uuid:
                        whitelist_data.append({"uuid": player_uuid, "name": name})

            # Completely overwrite the whitelist.json file
            whitelist_path = os.path.abspath(f"{WORLDS_DIR}/data/{server_id}/whitelist.json")
            async with aiofiles.open(whitelist_path, "w") as f:
                await f.write(json.dumps(whitelist_data, indent=2))

            # Force the server to read the newly created file
            await run_rcon("whitelist reload")

        return True


    async def _migrate_all_players(self, server_id: str, changing_to_online_mode: bool):
        """Finds all known players and bulk-migrates their data"""

        usernames = await self.get_all_known_usernames(server_id)

        if not usernames:
            return

        for username in usernames:
            await self._migrate_player_data(server_id, username, changing_to_online_mode)


    async def _migrate_player_data(self, server_id: str, username: str, changing_to_online_mode: bool) -> bool:
        """Migrate a player's save files between offline and online UUIDs"""

        offline_uuid = self.generate_offline_uuid(username)
        premium_uuid = await self.get_premium_uuid(username)

        if not premium_uuid:
            return False

        if changing_to_online_mode:
            src_uuid, dst_uuid = offline_uuid, premium_uuid
        else:
            src_uuid, dst_uuid = premium_uuid, offline_uuid

        world_dir = os.path.abspath(f"{WORLDS_DIR}/data/{server_id}/world/players")
        folders = ["data", "stats", "advancements"]

        for folder in folders:
            folder_path = os.path.join(world_dir, folder)
            if not os.path.exists(folder_path):
                continue

            for ext in [".dat", ".dat_old", ".json"]:
                src_file = os.path.join(folder_path, f"{src_uuid}{ext}")
                dst_file = os.path.join(folder_path, f"{dst_uuid}{ext}")

                if os.path.exists(src_file):
                    if os.path.exists(dst_file):
                        os.remove(dst_file)

                    os.rename(src_file, dst_file)

        return True


    @staticmethod
    async def get_all_known_usernames(server_id: str) -> list[str]:
        """Reads the server's usercache.json to find every unique username"""

        cache_path = os.path.abspath(f"{WORLDS_DIR}/data/{server_id}/usercache.json")

        if not os.path.exists(cache_path):
            return []

        try:
            async with aiofiles.open(cache_path, mode="r") as f:
                data = await f.read()

            json_data = json.loads(data)

            unique_usernames: set[str] = {entry["name"] for entry in json_data if "name" in entry}

            return list(unique_usernames)

        except Exception as e:
            print(f"Failed to read usercache.json for {server_id}")
            raise


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


    @staticmethod
    async def get_premium_uuid(username: str) -> str | None:
        """Fetches the official Mojang UUID for a purchased account"""

        try:
            url = f"https://api.mojang.com/users/profiles/minecraft/{username}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    return str(uuid.UUID(data["id"]))

        except ClientConnectionError:
            # TODO: log mc-router not working
            return None
