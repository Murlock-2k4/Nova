"""Compatibility launcher for Nova.

The preferred entry point is now:
    python -m uvicorn server.api:app --host 127.0.0.1 --port 8000

Running this file starts that same unified FastAPI application.
"""

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "server.api:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
