"""Telemetry exporters for bridging turret data to external systems."""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Callable, Protocol, runtime_checkable

try:  # pragma: no cover - optional dependency
    import websockets  # type: ignore
except Exception:  # pragma: no cover - fallback when websockets missing
    websockets = None


if websockets:

    async def _send_websocket_payload(uri: str, payload: str) -> None:
        async with websockets.connect(uri) as connection:  # type: ignore[operator]
            await connection.send(payload)

else:  # pragma: no cover - helper only used when websockets missing

    async def _send_websocket_payload(uri: str, payload: str) -> None:
        raise RuntimeError(
            "The 'websockets' package is required for WebSocketTelemetryExporter"
        )


def _telemetry_to_dict(telemetry: "TurretTelemetry") -> dict:
    data = asdict(telemetry)
    # Dataclasses like Vector3 are already converted by asdict.
    return data


@runtime_checkable
class TelemetryExporter(Protocol):
    """Minimal interface for streaming turret telemetry."""

    def send(self, telemetry: "TurretTelemetry") -> None:
        ...

    def close(self) -> None:
        ...


class WebSocketTelemetryExporter:
    """Push telemetry snapshots to a WebSocket endpoint as JSON."""

    def __init__(self, uri: str) -> None:
        self._uri = uri

    def send(self, telemetry: "TurretTelemetry") -> None:
        payload = json.dumps(_telemetry_to_dict(telemetry))
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_send_websocket_payload(self._uri, payload))
        else:  # pragma: no cover - exercised when embedded in async hosts
            loop.create_task(_send_websocket_payload(self._uri, payload))

    def close(self) -> None:  # pragma: no cover - nothing to tear down
        return None


class RpcTelemetryExporter:
    """Dispatch telemetry to an arbitrary RPC handler."""

    def __init__(self, dispatcher: Callable[[str, dict], None], method: str = "telemetry.update") -> None:
        self._dispatcher = dispatcher
        self._method = method

    def send(self, telemetry: "TurretTelemetry") -> None:
        self._dispatcher(self._method, _telemetry_to_dict(telemetry))

    def close(self) -> None:  # pragma: no cover - stateless
        return None


__all__ = [
    "TelemetryExporter",
    "WebSocketTelemetryExporter",
    "RpcTelemetryExporter",
]
