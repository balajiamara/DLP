"""
WebSocket Connection Manager Service

Manages active room-scoped WebSocket connections per classroom_id and enforces
proactive token-expiry socket disconnection via background asyncio tasks.
"""

import time
import asyncio
import logging
from collections import defaultdict
from fastapi import WebSocket, status

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Thread-safe room-scoped WebSocket connection manager.
    Rooms are keyed by integer classroom_id.
    """

    def __init__(self):
        self.active_rooms: dict[int, set[WebSocket]] = defaultdict(set)
        self.expiry_tasks: dict[WebSocket, asyncio.Task] = {}

    async def connect(self, classroom_id: int, websocket: WebSocket, exp_timestamp: float) -> None:
        """
        Registers an accepted WebSocket connection under classroom_id room
        and schedules a background task to disconnect when token expires.
        """
        self.active_rooms[classroom_id].add(websocket)
        logger.info(
            f"WebSocket connected: room classroom_{classroom_id} | Total active in room: {len(self.active_rooms[classroom_id])}"
        )

        remaining_seconds = exp_timestamp - time.time()
        if remaining_seconds > 0:
            task = asyncio.create_task(
                self._schedule_expiry_disconnect(classroom_id, websocket, remaining_seconds)
            )
            self.expiry_tasks[websocket] = task
        else:
            # Token already expired, schedule immediate disconnect
            task = asyncio.create_task(
                self._schedule_expiry_disconnect(classroom_id, websocket, 0.0)
            )
            self.expiry_tasks[websocket] = task

    async def disconnect(self, classroom_id: int, websocket: WebSocket) -> None:
        """
        Removes a WebSocket connection from active_rooms and cancels its expiry task.
        """
        if websocket in self.active_rooms[classroom_id]:
            self.active_rooms[classroom_id].remove(websocket)
            if not self.active_rooms[classroom_id]:
                del self.active_rooms[classroom_id]
            logger.info(f"WebSocket disconnected from room classroom_{classroom_id}.")

        task = self.expiry_tasks.pop(websocket, None)
        if task and not task.done():
            task.cancel()

    async def broadcast_to_room(self, room_id: int, message_data: dict) -> int:
        """
        Broadcasts a JSON-serializable message payload to all active WebSocket connections in room_id.

        Returns:
            Number of active clients successfully notified.
        """
        connections = self.active_rooms.get(room_id, set()).copy()
        if not connections:
            logger.debug(f"Broadcast ignored: 0 active WebSocket connections in room {room_id}.")
            return 0

        sent_count = 0
        stale_sockets = []

        for ws in connections:
            try:
                await ws.send_json(message_data)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send broadcast to WebSocket client in room {room_id}: {e}")
                stale_sockets.append(ws)

        # Cleanup any broken connections
        for ws in stale_sockets:
            await self.disconnect(room_id, ws)

        logger.info(
            f"Broadcast event '{message_data.get('event_type')}' delivered to {sent_count}/{len(connections)} clients in room {room_id}."
        )
        return sent_count

    async def broadcast_to_classroom(self, classroom_id: int, message_data: dict) -> int:
        return await self.broadcast_to_room(classroom_id, message_data)

    async def broadcast_to_conversation(self, conversation_id: int, message_data: dict) -> int:
        return await self.broadcast_to_room(conversation_id, message_data)

    async def _schedule_expiry_disconnect(
        self, classroom_id: int, websocket: WebSocket, remaining_seconds: float
    ) -> None:
        """Helper task to proactively close socket when token's exp timestamp is reached."""
        try:
            if remaining_seconds > 0:
                await asyncio.sleep(remaining_seconds)

            # Proactively close socket if still active
            if websocket in self.active_rooms.get(classroom_id, set()):
                logger.info(
                    f"Token expired for WebSocket client in room {classroom_id}. Proactively closing connection."
                )
                try:
                    await websocket.close(
                        code=status.WS_1008_POLICY_VIOLATION,
                        reason="Token expired",
                    )
                except Exception as e:
                    logger.debug(f"Error while closing expired WebSocket: {e}")
                finally:
                    await self.disconnect(classroom_id, websocket)

        except asyncio.CancelledError:
            pass


# Global singleton instance for doubts connection management
manager = ConnectionManager()

# Dedicated singleton instance for Unified Chat conversation connection management
conversation_manager = ConnectionManager()

