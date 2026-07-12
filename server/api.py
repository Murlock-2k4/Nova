import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from state import get_state, set_error, update_state

from brain import ask_nova
from logging_config import setup_logging
from router import route_command
from typing import Any


class AssistantStateResponse(BaseModel):
    status: str
    is_speaking: bool
    music_is_playing: bool
    last_user_message: str
    last_nova_response: str
    current_tool: str | None
    last_error: str | None
    updated_at: str

setup_logging()
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Nova API",
    description="Local API for the Nova voice assistant.",
    version="0.1.0",
)


# This allows a future browser dashboard to call Nova.
# We are limiting it to local development addresses for now.
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


class CommandResponse(BaseModel):
    command: str
    response: str
    source: str


class StatusResponse(BaseModel):
    status: str
    assistant: str


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
            response = str(
                route_result.response or "Command completed."
            )

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

        update_state(
            last_nova_response=error_response,
        )

        return error_response, "error"


@app.get("/")
def root():
    return {
        "name": "Nova API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/api/status", response_model=AssistantStateResponse)
def get_assistant_status():
    return AssistantStateResponse(**get_state())


@app.post("/api/command", response_model=CommandResponse)
def run_command(request: CommandRequest):
    logger.info("API command received: %s", request.command)

    response, source = process_command(request.command)

    logger.info(
        "API command completed source=%s",
        source,
    )

    return CommandResponse(
        command=request.command,
        response=response,
        source=source,
    )