from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.services import get_docker_server_manager
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
    name: str, server_manager: DockerServerManagerDependency
):
    server_manager.create_server(name)


@minecraft_server_router.post("/{id}/start")
async def start_minecraft_server(
    id: str, server_manager: DockerServerManagerDependency
):
    server_manager.start_server(id)


@minecraft_server_router.post("/{id}/stop")
async def stop_minecraft_server(id: str, server_manager: DockerServerManagerDependency):
    server_manager.stop_server(id)
