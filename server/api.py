import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from tools.music import (
    get_playback_state,
    next_track,
    pause_music,
    play_track_uri,
    previous_track,
    resume_music,
    search_tracks,
    set_volume,
)

from brain import ask_nova
from database import (
    clear_conversation_history,
    get_recent_messages,
    initialize_database,
    save_exchange,
)
from logging_config import setup_logging
from router import route_command
from state import (
    add_state_listener,
    get_state,
    remove_state_listener,
    set_error,
    update_state,
)


class AssistantStateResponse(BaseModel):
    status: str
    is_speaking: bool
    music_is_playing: bool
    last_user_message: str
    last_nova_response: str
    current_tool: str | None
    last_error: str | None
    updated_at: str


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()

        async with self._lock:
            self._connections.add(websocket)

        await websocket.send_json({
            "type": "state",
            "data": get_state(),
        })

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast_state(self, snapshot: dict[str, Any]) -> None:
        async with self._lock:
            connections = tuple(self._connections)

        disconnected: list[WebSocket] = []

        for websocket in connections:
            try:
                await websocket.send_json({
                    "type": "state",
                    "data": snapshot,
                })
            except Exception:
                disconnected.append(websocket)

        if disconnected:
            async with self._lock:
                for websocket in disconnected:
                    self._connections.discard(websocket)


setup_logging()
logger = logging.getLogger(__name__)
manager = ConnectionManager()
server_loop: asyncio.AbstractEventLoop | None = None


def queue_state_broadcast(snapshot: dict[str, Any]) -> None:
    """Safely forward state changes from Nova's worker threads to FastAPI."""
    if server_loop is None or server_loop.is_closed():
        return

    asyncio.run_coroutine_threadsafe(
        manager.broadcast_state(snapshot),
        server_loop,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    global server_loop

    initialize_database()
    server_loop = asyncio.get_running_loop()
    add_state_listener(queue_state_broadcast)
    logger.info("Nova WebSocket state broadcaster started")

    try:
        yield
    finally:
        remove_state_listener(queue_state_broadcast)
        server_loop = None
        logger.info("Nova WebSocket state broadcaster stopped")


app = FastAPI(
    title="Nova API",
    description="Local API for the Nova voice assistant.",
    version="0.3.0",
    lifespan=lifespan,
)

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

app.mount(
    "/static",
    StaticFiles(directory=str(WEB_DIR)),
    name="static",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CommandRequest(BaseModel):
    command: str = Field(
        min_length=1,
        max_length=2000,
        examples=["What's on my calendar today?"],
    )


class MusicSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)


class MusicTrackRequest(BaseModel):
    uri: str = Field(pattern=r"^spotify:track:")


class MusicVolumeRequest(BaseModel):
    volume_percent: int = Field(ge=0, le=100)


class CommandResponse(BaseModel):
    command: str
    response: str
    source: str


def process_command(command: str) -> tuple[str, str]:
    cleaned_command = command.strip()

    update_state(
        status="thinking",
        last_user_message=cleaned_command,
        last_nova_response="",
        current_tool=None,
        last_error=None,
    )

    try:
        route_result = route_command(cleaned_command)

        if route_result.handled:
            response = str(route_result.response or "Command completed.")

            update_state(
                status="idle",
                last_nova_response=response,
            )

            return response, "router"

        response = ask_nova(cleaned_command)

        update_state(
            status="idle",
            last_nova_response=response,
        )

        return response, "ai"

    except Exception as error:
        logger.exception("API command processing failed")

        error_response = "Nova could not process that request."

        set_error(str(error))
        update_state(last_nova_response=error_response)

        return error_response, "error"


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/status", response_model=AssistantStateResponse)
def get_assistant_status():
    # Retained as a fallback and for diagnostics/API clients.
    return AssistantStateResponse(**get_state())


@app.websocket("/ws/state")
async def state_websocket(websocket: WebSocket):
    await manager.connect(websocket)
    logger.info("Dashboard WebSocket connected")

    try:
        while True:
            # The browser sends a lightweight keepalive message periodically.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Dashboard WebSocket failed")
    finally:
        await manager.disconnect(websocket)
        logger.info("Dashboard WebSocket disconnected")


@app.post("/api/command", response_model=CommandResponse)
def run_command(request: CommandRequest):
    logger.info("API command received: %s", request.command)

    response, source = process_command(request.command)

    try:
        save_exchange(request.command, response, source)
    except Exception:
        logger.exception("Could not save conversation history")

    logger.info("API command completed source=%s", source)

    return CommandResponse(
        command=request.command,
        response=response,
        source=source,
    )


@app.get("/api/history")
def conversation_history(limit: int = 50):
    return {"messages": get_recent_messages(limit)}


@app.delete("/api/history")
def delete_conversation_history():
    deleted_count = clear_conversation_history()
    return {"deleted": deleted_count}


@app.get("/api/music/status")
def music_status():
    return get_playback_state()


@app.get("/api/music/search")
def music_search(query: str):
    return {"tracks": search_tracks(query)}


@app.post("/api/music/play")
def music_play(request: MusicTrackRequest):
    return {"message": play_track_uri(request.uri)}


@app.post("/api/music/pause")
def music_pause():
    return {"message": pause_music()}


@app.post("/api/music/resume")
def music_resume():
    return {"message": resume_music()}


@app.post("/api/music/next")
def music_next():
    return {"message": next_track()}


@app.post("/api/music/previous")
def music_previous():
    return {"message": previous_track()}


@app.post("/api/music/volume")
def music_volume(request: MusicVolumeRequest):
    return {"message": set_volume(request.volume_percent)}
