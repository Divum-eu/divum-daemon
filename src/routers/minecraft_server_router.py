"""
The router containing Minecraft server-related endpoints.
"""

import asyncio
from typing import Annotated, Union

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import Field

from dependencies.services import get_docker_server_manager
from exceptions.client_api_exception import ClientAPIException
from exceptions.docker_container_not_found_exception import (
    DockerContainerNotFoundException,
)
from schemas.minecraft_server_config.minecraft_fabric_server_config import (
    MinecraftFabricServerConfig,
)
from schemas.minecraft_server_config.minecraft_vanilla_server_config import (
    MinecraftVanillaServerConfig,
)
from services.minecraft.minecraft_server_manager import MinecraftServerManager

from utils.jwt_verification import verify_jwt_signature, verify_jwt_websocket

DockerServerManagerDependency = Annotated[
    MinecraftServerManager, Depends(get_docker_server_manager)
]

JwtSignatureDependency = Annotated[dict, Depends(verify_jwt_signature)]

minecraft_server_router = APIRouter(
    prefix="/v1/minecraft-servers",
    tags=["minecraft_servers"],
)

MinecraftServerConfig = Annotated[
    Union[MinecraftVanillaServerConfig, MinecraftFabricServerConfig],
    Field(discriminator="type"),
]


@minecraft_server_router.post("", status_code=200)
async def create_minecraft_server(
    request: MinecraftServerConfig,
    server_manager: DockerServerManagerDependency,
    jwtAuth: JwtSignatureDependency,
):
    """
    The endpoint for Minecraft server creation.
    """
    server_id: str | None = await server_manager.create(request)

    if not server_id:
        raise HTTPException(500, "A Minecraft server instance could not be created.")

    return server_id


@minecraft_server_router.post("/{id}/start", status_code=202)
async def start_minecraft_server(
    id: str,
    server_manager: DockerServerManagerDependency,
    jwtAuth: JwtSignatureDependency,
):
    """
    The endpoint for starting Minecraft server.
    """
    server_started: bool = await server_manager.start(id)

    if not server_started:
        raise HTTPException(
            404, "No Minecraft server instance exists with the given ID."
        )
    return


@minecraft_server_router.post("/{id}/stop", status_code=202)
async def stop_minecraft_server(
    id: str,
    server_manager: DockerServerManagerDependency,
    jwtAuth: JwtSignatureDependency,
):
    """
    The endpoint for stopping Minecraft server.
    """
    server_stopped: bool = await server_manager.stop(id)

    if not server_stopped:
        raise HTTPException(
            404, "No Minecraft server instance exists with the given ID."
        )


@minecraft_server_router.patch("/{id}", status_code=204)
async def update_minecraft_server(
    id: str,
    request: MinecraftServerConfig,
    server_manager: DockerServerManagerDependency,
    jwtAuth: JwtSignatureDependency,
):
    """
    The endpoint for updating a Minecraft server instance's configuration.
    """
    was_successful: bool = await server_manager.update(id, request)

    if not was_successful:
        raise HTTPException(
            404, "No Minecraft server instance exists with the given ID."
        )


@minecraft_server_router.delete("/{id}", status_code=204)
async def delete_minecraft_server(
    id: str,
    server_manager: DockerServerManagerDependency,
    jwtAuth: JwtSignatureDependency,
):
    """The endpoint for deleting a Minecraft server instance."""
    was_successful: bool = await server_manager.delete(id)

    if not was_successful:
        raise HTTPException(
            404, "No Minecraft server instance exists with the given ID."
        )


@minecraft_server_router.websocket("/{id}/status/ws")
async def get_minecraft_server_status(
    websocket: WebSocket, id: str, server_manager: DockerServerManagerDependency
):
    """A websocket endpoint for sending server status every three seconds."""

    try:
        await verify_jwt_websocket(websocket)
        await websocket.accept()

        while True:
            server_status = await server_manager.get_status(id)

            await websocket.send_json(server_status.model_dump())

            await asyncio.sleep(3)
    except (ClientAPIException, DockerContainerNotFoundException) as ex:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(ex))
    except WebSocketDisconnect:
        pass
