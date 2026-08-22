"""
WebSocket connection manager for WS /live.

Recognition/attendance/alert logic runs on a background thread (see
recognition_service.py), not on FastAPI's asyncio event loop, so broadcasting
from there needs asyncio.run_coroutine_threadsafe rather than a plain
`await`. main.py's startup event captures the running loop via
set_event_loop() so ConnectionManager.broadcast() can safely be called from
any thread.
"""
import asyncio
import json
import logging
import threading

from fastapi import WebSocket

logger = logging.getLogger("ws")


def _json_default(o):
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []
        self._connections_lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        with self._connections_lock:
            self._connections.append(websocket)
        logger.info(f"WS client connected ({len(self._connections)} total).")

    def disconnect(self, websocket: WebSocket):
        with self._connections_lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info(f"WS client disconnected ({len(self._connections)} total).")

    async def _broadcast_async(self, message: dict):
        text = json.dumps(message, default=_json_default)
        with self._connections_lock:
            connections = list(self._connections)
        for ws in connections:
            try:
                await ws.send_text(text)
            except Exception:
                self.disconnect(ws)

    def broadcast(self, message: dict):
        """Thread-safe: call this from the recognition worker's background
        thread (or anywhere else) to push an event to all connected clients."""
        if self._loop is None:
            logger.warning(f"Event loop not ready yet; dropping broadcast: {message}")
            return
        asyncio.run_coroutine_threadsafe(self._broadcast_async(message), self._loop)


# Single shared instance.
ws_manager = ConnectionManager()
