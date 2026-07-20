"""
WebSocket Connection Manager with RBAC support.

Connections are tagged with a role (VIEWER/OPERATOR/ADMIN) and can
receive messages filtered by minimum role level. This enables:
  - Broadcasting operational events to all connected clients
  - Sending admin-only events (audit, user changes) only to ADMIN connections
  - Sending remediation events only to OPERATOR+ connections
"""
import hashlib
import hmac
import os
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Dict, List, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSRole(IntEnum):
    """Mirror of backend.rbac.Role for WebSocket context."""
    VIEWER = 1
    OPERATOR = 2
    ADMIN = 3


@dataclass
class WSConnection:
    """A WebSocket connection with RBAC metadata."""
    websocket: WebSocket
    role: WSRole
    username: str = "anonymous"
    connected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    subscriptions: Set[str] = field(default_factory=lambda: {"all"})


class ConnectionManager:
    """Role-aware WebSocket connection manager."""

    def __init__(self):
        self.active: List[WSConnection] = []

    async def connect(self, ws: WebSocket, role: WSRole, username: str = "anonymous") -> WSConnection:
        """Accept a WebSocket connection and register it with role metadata."""
        await ws.accept()
        conn = WSConnection(websocket=ws, role=role, username=username)
        self.active.append(conn)
        logger.info(f"[ws] connected: {username} (role={role.name}, total={len(self.active)})")
        return conn

    def disconnect(self, ws: WebSocket):
        """Remove a connection by its WebSocket reference."""
        self.active = [c for c in self.active if c.websocket is not ws]

    async def broadcast(self, message: dict, min_role: WSRole = WSRole.VIEWER, channel: str = "all"):
        """
        Send a message to all connections that meet the minimum role requirement
        and are subscribed to the given channel.

        Args:
            message: JSON-serializable message payload.
            min_role: Minimum role required to receive this message.
            channel: Channel filter — "all" matches everyone subscribed to "all".
        """
        dead = []
        for conn in self.active:
            if conn.role < min_role:
                continue
            if channel != "all" and channel not in conn.subscriptions:
                continue
            try:
                await conn.websocket.send_json(message)
            except Exception:
                dead.append(conn.websocket)
        for ws in dead:
            self.disconnect(ws)

    async def send_to_user(self, username: str, message: dict):
        """Send a message to a specific connected user."""
        dead = []
        for conn in self.active:
            if conn.username == username:
                try:
                    await conn.websocket.send_json(message)
                except Exception:
                    dead.append(conn.websocket)
        for ws in dead:
            self.disconnect(ws)

    def get_connection_count(self) -> int:
        return len(self.active)

    def get_connections_info(self) -> List[dict]:
        """Return connection info (for admin status endpoint)."""
        return [
            {
                "username": c.username,
                "role": c.role.name,
                "connected_at": c.connected_at,
                "subscriptions": list(c.subscriptions),
            }
            for c in self.active
        ]

    async def close_all(self):
        for conn in list(self.active):
            try:
                await conn.websocket.close()
            except Exception:
                pass
        self.active.clear()


async def authenticate_websocket(api_key: Optional[str]) -> Optional[tuple]:
    """
    Authenticate a WebSocket connection using the same RBAC logic as HTTP routes.
    Async — DB lookup is wrapped in asyncio.to_thread to avoid blocking the event loop.

    Returns (role: WSRole, username: str) or None if authentication fails.
    """
    if not api_key:
        return None

    # Check env-var role keys first (no I/O — safe to do synchronously)
    role_keys = {
        WSRole.ADMIN: os.getenv("API_KEY_ADMIN"),
        WSRole.OPERATOR: os.getenv("API_KEY_OPERATOR"),
        WSRole.VIEWER: os.getenv("API_KEY_VIEWER"),
    }
    for role, key in role_keys.items():
        if key and hmac.compare_digest(api_key, key):
            return (role, f"env:{role.name.lower()}")

    # Legacy key → operator
    legacy_key = os.getenv("API_KEY")
    if legacy_key and hmac.compare_digest(api_key, legacy_key):
        return (WSRole.OPERATOR, "env:legacy")

    # Check user-managed keys in the database — wrapped in to_thread to avoid blocking
    import asyncio

    def _db_lookup() -> Optional[tuple]:
        try:
            from backend.database import query_one, DB_TYPE
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            placeholder = "%s" if DB_TYPE == "postgres" else "?"
            sql = f"SELECT username, role, is_active, key_expires_at FROM users WHERE api_key_hash={placeholder}"
            user = query_one(sql, (key_hash,))
            if not user:
                return None
            if not user.get("is_active", True):
                return None
            expires_at = user.get("key_expires_at")
            if expires_at:
                try:
                    expiry = datetime.fromisoformat(expires_at)
                    if expiry < datetime.now(timezone.utc):
                        return None
                except (ValueError, TypeError):
                    pass
            role_str = user.get("role", "viewer").upper()
            ws_role = WSRole[role_str]
            return (ws_role, user["username"])
        except Exception as e:
            logger.warning(f"[ws] user key lookup failed: {e}")
            return None

    return await asyncio.to_thread(_db_lookup)


manager = ConnectionManager()
