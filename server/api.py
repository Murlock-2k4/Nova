import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from tools.alarms import create_alarm, list_alarms, load_saved_alarms, remove_alarm, update_alarm
from tools.calendar_tools import get_calendar_events

from tools.music import (
    get_devices,
    get_playback_state,
    next_track,
    pause_music,
    play_track_uri,
    previous_track,
    resume_music,
    search_tracks,
    select_device,
    set_volume,
)

from database import (
    clear_conversation_history,
    create_room,
    get_client,
    get_recent_messages,
    initialize_database,
    list_rooms,
    register_client,
    touch_client,
)
from logging_config import setup_logging
from voice_service import voice_service
from conversation_service import process_and_record
from state import (
    add_state_listener,
    get_state,
    remove_state_listener,
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
    load_saved_alarms()
    voice_service.start()
    logger.info("Nova application services started")

    try:
        yield
    finally:
        voice_service.stop()
        remove_state_listener(queue_state_broadcast)
        server_loop = None
        logger.info("Nova application services stopped")


app = FastAPI(
    title="Nova API",
    description="Local API for the Nova voice assistant.",
    version="0.4.0",
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
    client_id: str | None = Field(default=None, max_length=120)
    command: str = Field(
        min_length=1,
        max_length=2000,
        examples=["What's on my calendar today?"],
    )


class RoomCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ClientRegisterRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=80)
    room_id: int | None = Field(default=None, ge=1)


class MusicSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)


class MusicTrackRequest(BaseModel):
    uri: str = Field(pattern=r"^spotify:track:")


class MusicVolumeRequest(BaseModel):
    volume_percent: int = Field(ge=0, le=100)


class MusicDeviceRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=200)


class AlarmCreateRequest(BaseModel):
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    days: list[int] = Field(min_length=1, max_length=7)
    label: str = Field(default="Morning routine", max_length=120)
    enabled: bool = True


class AlarmUpdateRequest(BaseModel):
    enabled: bool


class CommandResponse(BaseModel):
    command: str
    response: str
    source: str
    client_id: str | None = None
    room_id: int | None = None
    room_name: str | None = None


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
    registered_client_id: str | None = None
    logger.info("Dashboard WebSocket connected")

    try:
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")

            if message_type == "register":
                client = register_client(
                    client_id=str(message.get("client_id", "")),
                    name=str(message.get("name", "Nova Display")),
                    room_id=message.get("room_id"),
                )
                registered_client_id = client["id"]
                await websocket.send_json({
                    "type": "client_registered",
                    "data": client,
                })
            elif message_type == "ping" and registered_client_id:
                touch_client(registered_client_id)
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Dashboard WebSocket failed")
    finally:
        await manager.disconnect(websocket)
        logger.info("Dashboard WebSocket disconnected")


@app.post("/api/command", response_model=CommandResponse)
def run_command(request: CommandRequest):
    logger.info(
        "API command received client_id=%s command=%s",
        request.client_id,
        request.command,
    )

    client = get_client(request.client_id) if request.client_id else None
    response, source = process_and_record(
        request.command,
        client_id=client["id"] if client else None,
        room_id=client["room_id"] if client else None,
        source_prefix="chat",
    )

    logger.info("API command completed source=%s", source)

    return CommandResponse(
        command=request.command,
        response=response,
        source=source,
        client_id=client["id"] if client else None,
        room_id=client["room_id"] if client else None,
        room_name=client["room_name"] if client else None,
    )


@app.get("/api/rooms")
def get_rooms():
    return {"rooms": list_rooms()}


@app.post("/api/rooms")
def add_room(request: RoomCreateRequest):
    return {"room": create_room(request.name)}


@app.get("/api/clients/{client_id}")
def read_client(client_id: str):
    client = get_client(client_id)
    return {"client": client}


@app.put("/api/clients/{client_id}")
def update_client(client_id: str, request: ClientRegisterRequest):
    if request.client_id != client_id:
        raise ValueError("Client ID in the path and body must match")
    return {
        "client": register_client(
            request.client_id,
            request.name,
            request.room_id,
        )
    }


@app.get("/api/history")
def conversation_history(limit: int = 50):
    return {"messages": get_recent_messages(limit)}


@app.delete("/api/history")
def delete_conversation_history():
    deleted_count = clear_conversation_history()
    return {"deleted": deleted_count}


@app.get("/api/music/devices")
def music_devices():
    return {"devices": get_devices()}


@app.post("/api/music/device")
def music_select_device(request: MusicDeviceRequest):
    return {"message": select_device(request.device_id)}


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


@app.get("/api/calendar/events")
def calendar_events(days: int = 7):
    return {"events": get_calendar_events(days=days)}


@app.get("/api/alarms")
def alarms_list():
    return {"alarms": list_alarms()}


@app.post("/api/alarms")
def alarms_create(request: AlarmCreateRequest):
    alarm = create_alarm(
        request.time,
        request.days,
        request.label,
        request.enabled,
    )
    return {"alarm": alarm, "message": "Weekly alarm created."}


@app.patch("/api/alarms/{alarm_id}")
def alarms_update(alarm_id: str, request: AlarmUpdateRequest):
    alarm = update_alarm(alarm_id, enabled=request.enabled)
    return {
        "alarm": alarm,
        "updated": alarm is not None,
        "message": "Alarm updated." if alarm else "Alarm not found.",
    }


@app.delete("/api/alarms/{alarm_id}")
def alarms_delete(alarm_id: str):
    removed = remove_alarm(alarm_id)
    return {
        "removed": removed,
        "message": "Alarm deleted." if removed else "Alarm not found.",
    }
