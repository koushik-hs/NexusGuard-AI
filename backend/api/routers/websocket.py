"""
WebSocket router — /api/ws

Broadcasts LiveUpdate messages to all connected clients in real time.
Clients receive a JSON message for every processed event.

Connection lifecycle:
  - Client connects to ws://localhost:8000/api/ws
  - Server sends a "connected" handshake with current system status
  - Server broadcasts all future LiveUpdate messages to all connected clients
  - Client can disconnect at any time

Fan-out is handled via an in-memory set of queues — one per connected client.
This avoids any external broker dependency for the synthetic dataset scale.
"""

import asyncio
import json
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

# Global set of active WebSocket connections
_active_connections: Set[WebSocket] = set()


async def broadcast(message: dict):
    """Broadcast a message to all currently connected WebSocket clients."""
    if not _active_connections:
        return

    data = json.dumps(message, default=str)
    dead = set()
    for ws in list(_active_connections):
        try:
            await ws.send_text(data)
        except Exception:
            dead.add(ws)

    for ws in dead:
        _active_connections.discard(ws)


@router.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint.
    
    Sends a handshake on connect, then streams all LiveUpdate messages.
    The client should handle reconnection (e.g. on 1006 close).
    """
    await websocket.accept()
    _active_connections.add(websocket)

    try:
        # Send handshake with current system status
        from realtime.state import live_state
        status = live_state.get_status()
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "NexusGuard AI real-time stream connected",
            "system_status": status,
        }))

        # Keep connection alive — actual data is pushed via broadcast()
        while True:
            try:
                # Wait for client ping/pong or disconnect
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Echo pings back as pongs
                if msg == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                # Send keepalive
                try:
                    await websocket.send_text(json.dumps({"type": "keepalive"}))
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    finally:
        _active_connections.discard(websocket)
