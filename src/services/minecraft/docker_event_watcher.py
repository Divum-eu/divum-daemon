import asyncio
import json
import os
import threading

import docker
from pydantic import TypeAdapter

from routers.minecraft_server_router import MinecraftServerConfig
from services.minecraft.server_manager import ServerManager

WORLDS_DIR = os.getenv("WORLDS_DIR", "../..")

class DockerEventWatcher:
    def __init__(self, server_manager: ServerManager, main_loop: asyncio.AbstractEventLoop):
        self._server_manager: ServerManager = server_manager
        self._client = docker.from_env()
        self._main_loop: asyncio.AbstractEventLoop = main_loop
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._listen_for_stops, daemon=True)
        self._thread.start()

    def _listen_for_stops(self):
        filters = {"type": "container", "event": ["stop", "die"]}

        for event in self._client.events(decode=True, filters=filters):
            container_name = event["Actor"]["Attributes"].get("name")
            if not container_name:
                continue

            pending_path = os.path.abspath(f"{WORLDS_DIR}/data/{container_name}/.pending_config.json")

            if os.path.exists(pending_path):
                try:
                    with open(pending_path, "r") as f:
                        config_data = f.read()
                        pending_config = TypeAdapter(MinecraftServerConfig).validate_json(config_data)

                        os.remove(pending_path)

                        future = asyncio.run_coroutine_threadsafe(
                            self._server_manager.update(container_name, pending_config),
                            self._main_loop
                        )
                        future.result()
                except Exception as e:
                    print(f"Failed to apply pending config for {container_name}: {e}")

