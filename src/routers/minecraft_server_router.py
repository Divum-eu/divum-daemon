"""
The router containing Minecraft server-related endpoints.
"""

from typing import Annotated, Union

from pydantic import Field

from fastapi import APIRouter, Depends, HTTPException

from dependencies.services import get_docker_server_manager

from services.server_manager import ServerManager

from schemas.minecraft_server_config.minecraft_fabric_server_config import (
    MinecraftFabricServerConfig,
)
from schemas.minecraft_server_config.minecraft_vanilla_server_config import (
    MinecraftVanillaServerConfig,
)


DockerServerManagerDependency = Annotated[
    ServerManager, Depends(get_docker_server_manager)
]

minecraft_server_router = APIRouter(
    prefix="/minecraft-servers",
    tags=["minecraft_servers"],
)

MinecraftServerConfig = Annotated[
    Union[MinecraftVanillaServerConfig, MinecraftFabricServerConfig],
    Field(discriminator="type"),
]


@minecraft_server_router.post("/", status_code=200)
async def create_minecraft_server(
    request: MinecraftServerConfig, server_manager: DockerServerManagerDependency
):
    """
    The endpoint for Minecraft server creation.
    """
    server_id: str | None = await server_manager.create(request)

    if not server_id:
        raise HTTPException(500, "Server could not be created.")

    return server_id


@minecraft_server_router.post("/{id}/start", status_code=200)
async def start_minecraft_server(
    id: str, server_manager: DockerServerManagerDependency
):
    """
    The endpoint for starting Minecraft server containers.
    """
    server_started: bool = await server_manager.start(id)

    if not server_started:
        raise HTTPException(404, "Server not found.")
    return


@minecraft_server_router.post("/{id}/stop")
async def stop_minecraft_server(id: str, server_manager: DockerServerManagerDependency):
    """
    The endpoint for stopping Minecraft server containers.
    """
    server_stopped: bool = await server_manager.stop(id)

    if not server_stopped:
        raise HTTPException(404, "Server not found.")
