"""Turret AI package exposing the main control classes."""
from __future__ import annotations

from .exporters import (
    CaptureOverlayTelemetryExporter,
    RpcTelemetryExporter,
    TelemetryExporter,
    WebSocketTelemetryExporter,
)
from .geometry import UP, Vector3, solve_intercept_time
from .turret import (
    AmmunitionType,
    ManualWaypoint,
    ObstructionSample,
    Target,
    TargetDesignation,
    Turret,
    TurretConfig,
    TurretState,
    TurretTelemetry,
)

__all__ = [
    "AmmunitionType",
    "ManualWaypoint",
    "ObstructionSample",
    "Target",
    "TargetDesignation",
    "Turret",
    "TurretConfig",
    "TurretState",
    "TurretTelemetry",
    "Vector3",
    "UP",
    "solve_intercept_time",
    "TelemetryExporter",
    "WebSocketTelemetryExporter",
    "RpcTelemetryExporter",
    "CaptureOverlayTelemetryExporter",
]
