from fastapi import APIRouter, FastAPI

from src.routers.minecraft_server_router import minecraft_server_router

app = FastAPI(
    title="DivumDaemon", swagger_ui_parameters={"syntaxHighlight": {"theme": "dracula"}}
)

main_router = APIRouter(prefix="/api/v1")
main_router.include_router(minecraft_server_router)

app.include_router(main_router)
