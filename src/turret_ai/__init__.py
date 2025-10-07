"""Turret AI package exposing the main control classes."""
from .geometry import Vector3, UP, solve_intercept_time
from .exporters import RpcTelemetryExporter, TelemetryExporter, WebSocketTelemetryExporter
from .turret import (
    AmmunitionType,
    ManualWaypoint,
    ObstructionSample,
    TargetDesignation,
    Target,
    Turret,
    TurretConfig,
    TurretState,
    TurretTelemetry,
)

__all__ = [
    "AmmunitionType",
    "ManualWaypoint",
    "ObstructionSample",
    "TargetDesignation",
    "Target",
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
]

