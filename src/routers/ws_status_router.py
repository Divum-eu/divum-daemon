import asyncio
import json
import os
from typing import Annotated
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import ValidationError

from dependencies.services import get_docker_server_manager
from schemas.server_status_update import ServerStatusUpdate
from schemas.watch_command import WatchCommand
from services.minecraft.server_manager import ServerManager
from services.minecraft.status_collector import collect_status

ws_status_router = APIRouter(
    tags=["minecraft_servers_ws"]
)

DockerServerManagerDependency = Annotated[
    ServerManager, Depends(get_docker_server_manager)
]

POLL_INTERVAL = int(os.environ.get("STATUS_POLL_INTERVAL_SECONDS", "3"))

@ws_status_router.websocket("/ws/status")
async def websocket_status_endpoint(websocket: WebSocket, server_manager: DockerServerManagerDependency):
    await websocket.accept()
    
    watched_servers: set[str] = set()
    poll_tasks: dict[str, asyncio.Task] = {}
    
    async def poll_loop(server_id: str):
        while True:
            try:
                status_dict = await collect_status(server_manager, server_id)
                update = ServerStatusUpdate(**status_dict)
                await websocket.send_text(update.model_dump_json())
            except Exception as e:
                print(f"Error in poll loop for {server_id}: {e}")
            await asyncio.sleep(POLL_INTERVAL)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                json_data = json.loads(data)
                command = WatchCommand(**json_data)
                server_id = command.server_id
                
                if command.type == "watch":
                    if server_id not in watched_servers:
                        watched_servers.add(server_id)
                        poll_tasks[server_id] = asyncio.create_task(poll_loop(server_id))
                elif command.type == "unwatch":
                    if server_id in watched_servers:
                        watched_servers.remove(server_id)
                        task = poll_tasks.pop(server_id, None)
                        if task:
                            task.cancel()
            except (json.JSONDecodeError, ValidationError) as e:
                print(f"Invalid WS message received: {e}")
    except WebSocketDisconnect:
        # Cancel all running poll tasks
        for task in poll_tasks.values():
            task.cancel()
