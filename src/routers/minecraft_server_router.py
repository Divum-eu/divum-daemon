from typing import Annotated, Union

from fastapi import APIRouter, Depends
from pydantic import Field

from dependencies.services import get_docker_server_manager
from schemas.minecraft_server_itzg_config import MinecraftServerITZGConfig

from schemas.minecraft_server_config.minecraft_fabric_server_config import MinecraftFabricServerConfig
from schemas.minecraft_server_config.minecraft_vanilla_server_config import MinecraftVanillaServerConfig
from services.server_manager import ServerManager

DockerServerManagerDependency = Annotated[
    ServerManager, Depends(get_docker_server_manager)
]

minecraft_server_router = APIRouter(
    prefix="/minecraft-servers",
    tags=["minecraft_servers"],
)

MinecraftConfig = Annotated[
    Union[MinecraftVanillaServerConfig, MinecraftFabricServerConfig],
    Field(discriminator="type")
]

@minecraft_server_router.post("/")
async def create_minecraft_server(
    request: MinecraftConfig, server_manager: DockerServerManagerDependency
):
    server_manager.create(request)


@minecraft_server_router.post("/{id}/start")
async def start_minecraft_server(
    id: str, server_manager: DockerServerManagerDependency
):
    server_manager.start(id)


@minecraft_server_router.post("/{id}/stop")
async def stop_minecraft_server(id: str, server_manager: DockerServerManagerDependency):
    server_manager.stop(id)
