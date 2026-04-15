from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.services import get_docker_server_manager
from schemas.minecraft_server_itzg_config import MinecraftServerITZGConfig
from services.server_manager import ServerManager

DockerServerManagerDependency = Annotated[
    ServerManager, Depends(get_docker_server_manager)
]

minecraft_server_router = APIRouter(
    prefix="/minecraft-servers",
    tags=["minecraft_servers"],
)


@minecraft_server_router.post("/")
async def create_minecraft_server(
    request: MinecraftServerITZGConfig, server_manager: DockerServerManagerDependency
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
