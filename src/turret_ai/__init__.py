"""Turret AI package exposing the main control classes."""
from .geometry import Vector3, UP, solve_intercept_time
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
from .turret import Target, Turret, TurretConfig, TurretState

__all__ = [
    "Target",
    "Turret",
    "TurretConfig",
    "TurretState",
    "TurretTelemetry",
    "Vector3",
    "UP",
    "solve_intercept_time",
]

