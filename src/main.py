from dotenv import load_dotenv

load_dotenv()

import asyncio
from contextlib import asynccontextmanager


from dependencies.services import get_docker_server_manager, get_mc_proxy_router
from services.minecraft.docker_event_watcher import DockerEventWatcher

from fastapi import APIRouter, FastAPI

from routers.minecraft_server_router import minecraft_server_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    main_loop = asyncio.get_running_loop()
    router = get_mc_proxy_router()
    server_manager = get_docker_server_manager(router)
    watcher = DockerEventWatcher(server_manager, main_loop)
    watcher.start()
    yield

app = FastAPI(
    title="DivumDaemon",
    swagger_ui_parameters={"syntaxHighlight": {"theme": "dracula"}},
    lifespan=lifespan
)

main_router = APIRouter(prefix="/api/v1")
main_router.include_router(minecraft_server_router)

app.include_router(main_router)
