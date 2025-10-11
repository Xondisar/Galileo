"""Core turret AI logic with predictive aiming and cooperative designations."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .geometry import Vector3, solve_intercept_time


@dataclass(frozen=True)
class AmmunitionType:
    """Defines the characteristics of a projectile fired by the turret."""

    name: str
    projectile_speed: float
    damage: float
    heat_per_shot: float = 1.0


@dataclass(frozen=True)
class ManualWaypoint:
    """Manual override waypoint used for scripted behaviours."""

    position: Vector3
    linger: float = 0.0


@dataclass(frozen=True)
class ObstructionSample:
    """Result data from the obstruction callback for complex environments."""

    blocked: bool
    hit_position: Optional[Vector3] = None
    surface_normal: Optional[Vector3] = None
    navigation_cost: float = 0.0


@dataclass(frozen=True)
class TargetDesignation:
    """Threat data shared by allied sensors."""

    target_id: str
    threat: float
    ttl: float = 2.0
    sensor_id: Optional[str] = None
    sensor_kind: str = "generic"
    confidence: float = 1.0
    latency: float = 0.0


@dataclass(frozen=True)
class Target:
    """Represents an enemy actor tracked by the turret."""

    id: str
    position: Vector3
    velocity: Vector3
    is_airborne: bool = False
    priority: int = 0

    def predict_position(self, time: float) -> Vector3:
        return self.position + self.velocity * time


@dataclass
class TurretConfig:
    """Configuration tuning the turret responsiveness."""

    max_turn_rate_deg: float = 120.0
    max_elevation_deg: float = 60.0
    min_elevation_deg: float = -10.0
    fire_arc_deg: float = 5.0
    projectile_speed: float = 55.0
    detection_radius: float = 60.0
    target_memory: float = 1.5
    max_prediction_time: float = 3.0
    fire_cooldown: float = 0.2
    ammunition_types: Sequence[AmmunitionType] = field(default_factory=tuple)
    default_ammunition: Optional[str] = None
    obstruction_check: Optional[Callable[[Vector3, Vector3], object]] = None
    obstruction_feedback: Optional[Callable[[ObstructionSample], None]] = None
    orientation_blend: Optional[Callable[[float, float], Tuple[float, float]]] = None
    cooperative_threat_weight: float = 1.0
    cooperative_latency_decay: float = 0.5
    cooperative_confidence_exponent: float = 1.0
    telemetry_callback: Optional[Callable[["TurretTelemetry"], None]] = None
    effects_callback: Optional[Callable[["TurretTelemetry"], None]] = None
    idle_scan_speed_deg: float = 25.0
    idle_scan_yaw_range_deg: float = 45.0
    idle_scan_pitch_deg: float = 6.0


@dataclass
class TurretState:
    """Mutable state captured for telemetry."""

    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    cooldown: float = 0.0
    tracked_target: Optional[Target] = None
    time_since_last_seen: float = 0.0
    total_time: float = 0.0
    manual_waypoints: List[ManualWaypoint] = field(default_factory=list)
    waypoint_timer: float = 0.0
    waypoint_index: int = 0
    cooperative_designations: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class TurretTelemetry:
    """Snapshot of the turret state for external dashboards."""

    time: float
    yaw_deg: float
    pitch_deg: float
    tracked_target: Optional[str]
    prediction_time: float
    fired_target: Optional[str]
    obstruction: Optional[ObstructionSample]
    cooperative_designation_count: int


class Turret:
    """Pan/tilt turret controller supporting predictive firing."""

    def __init__(self, position: Vector3, config: Optional[TurretConfig] = None) -> None:
        self.position = position
        self.config = config or TurretConfig()
        self.state = TurretState()

    # ------------------------------------------------------------------
    # Target selection and cooperative designations
    # ------------------------------------------------------------------
    def ingest_designations(self, designations: Iterable[TargetDesignation]) -> None:
        for designation in designations:
            weight = designation.confidence ** self.config.cooperative_confidence_exponent
            latency_weight = math.exp(-designation.latency * self.config.cooperative_latency_decay)
            self.state.cooperative_designations[designation.target_id] = (
                designation.threat * weight * latency_weight
            )

    def _decay_designations(self, dt: float) -> None:
        to_remove: List[str] = []
        for target_id, threat in self.state.cooperative_designations.items():
            new_threat = threat * math.exp(-dt * self.config.cooperative_latency_decay)
            if new_threat <= 1e-3:
                to_remove.append(target_id)
            else:
                self.state.cooperative_designations[target_id] = new_threat
        for target_id in to_remove:
            self.state.cooperative_designations.pop(target_id, None)

    def select_target(self, targets: Sequence[Target]) -> Optional[Target]:
        if not targets:
            return None

        detection_sq = self.config.detection_radius ** 2
        in_range = [
            target
            for target in targets
            if (target.position - self.position).squared_magnitude() <= detection_sq
        ]
        if not in_range:
            return None

        def sort_key(target: Target) -> Tuple[float, float]:
            designation = self.state.cooperative_designations.get(target.id, 0.0)
            score = target.priority + self.config.cooperative_threat_weight * designation
            return (-score, self.position.distance_to(target.position))

        return min(in_range, key=sort_key)

    # ------------------------------------------------------------------
    # Update loop
    # ------------------------------------------------------------------
    def update(self, dt: float, visible_targets: Sequence[Target]) -> Optional[str]:
        self.state.total_time += dt
        self._decay_designations(dt)

        target = self.select_target(visible_targets)
        if target is None:
            target = self._handle_idle(dt)
        else:
            self.state.tracked_target = target
            self.state.time_since_last_seen = 0.0

        fired_target: Optional[str] = None
        obstruction: Optional[ObstructionSample] = None
        prediction_time = 0.0

        if target is not None:
            desired_yaw, desired_pitch, prediction_time = self._compute_desired_angles(target)
            self._apply_orientation(desired_yaw, desired_pitch, dt)

            if self._within_fire_arc(desired_yaw, desired_pitch) and self.state.cooldown <= 0:
                obstruction = self._check_obstruction(target)
                if not obstruction or not obstruction.blocked:
                    fired_target = target.id
                    self.state.cooldown = max(self.config.fire_cooldown, 1e-6)
        else:
            self.state.tracked_target = None
            self.state.time_since_last_seen += dt
            self._apply_idle_scan(dt)

        self.state.cooldown = max(0.0, self.state.cooldown - dt)

        telemetry = TurretTelemetry(
            time=self.state.total_time,
            yaw_deg=self.state.yaw_deg,
            pitch_deg=self.state.pitch_deg,
            tracked_target=self.state.tracked_target.id if self.state.tracked_target else None,
            prediction_time=prediction_time,
            fired_target=fired_target,
            obstruction=obstruction,
            cooperative_designation_count=len(self.state.cooperative_designations),
        )
        if self.config.telemetry_callback:
            self.config.telemetry_callback(telemetry)
        if self.config.effects_callback:
            self.config.effects_callback(telemetry)

        return fired_target

    # ------------------------------------------------------------------
    # Orientation helpers
    # ------------------------------------------------------------------
    def _handle_idle(self, dt: float) -> Optional[Target]:
        if self.state.tracked_target:
            self.state.time_since_last_seen += dt
            if self.state.time_since_last_seen > self.config.target_memory:
                self.state.tracked_target = None
        return self.state.tracked_target

    def _apply_orientation(self, desired_yaw: float, desired_pitch: float, dt: float) -> None:
        max_delta = self.config.max_turn_rate_deg * dt
        yaw_delta = self._normalize_angle(desired_yaw - self.state.yaw_deg)
        pitch_delta = max(
            -max_delta,
            min(max_delta, desired_pitch - self.state.pitch_deg),
        )
        yaw_delta = max(-max_delta, min(max_delta, yaw_delta))

        self.state.yaw_deg = self._normalize_angle(self.state.yaw_deg + yaw_delta)
        self.state.pitch_deg = max(
            self.config.min_elevation_deg,
            min(self.config.max_elevation_deg, self.state.pitch_deg + pitch_delta),
        )

        if self.config.orientation_blend:
            blended_yaw, blended_pitch = self.config.orientation_blend(
                self.state.yaw_deg, self.state.pitch_deg
            )
            self.state.yaw_deg = blended_yaw
            self.state.pitch_deg = blended_pitch

    def _apply_idle_scan(self, dt: float) -> None:
        yaw_range = self.config.idle_scan_yaw_range_deg
        pitch_range = self.config.idle_scan_pitch_deg
        speed = self.config.idle_scan_speed_deg
        offset = math.sin(self.state.total_time * math.radians(speed))
        self.state.yaw_deg = self._normalize_angle(offset * yaw_range)
        self.state.pitch_deg = max(
            self.config.min_elevation_deg,
            min(self.config.max_elevation_deg, offset * pitch_range),
        )

    def _compute_desired_angles(self, target: Target) -> Tuple[float, float, float]:
        projectile_speed = self._active_projectile_speed()
        intercept_position, intercept_time = self._predict_intercept(target, projectile_speed)
        offset = intercept_position - self.position
        distance = offset.magnitude()
        if distance == 0:
            return self.state.yaw_deg, self.state.pitch_deg, intercept_time

        yaw_rad = math.atan2(offset.x, offset.z)
        pitch_rad = math.asin(max(-1.0, min(1.0, offset.y / distance)))
        return math.degrees(yaw_rad), math.degrees(pitch_rad), intercept_time

    def _predict_intercept(self, target: Target, projectile_speed: float) -> Tuple[Vector3, float]:
        intercept_time = solve_intercept_time(
            origin=self.position,
            target_position=target.position,
            target_velocity=target.velocity,
            projectile_speed=projectile_speed,
            max_time=self.config.max_prediction_time,
        )
        intercept_time = max(0.0, intercept_time)
        predicted_position = target.predict_position(intercept_time)
        return predicted_position, intercept_time

    def _within_fire_arc(self, desired_yaw: float, desired_pitch: float) -> bool:
        yaw_error = abs(self._normalize_angle(desired_yaw - self.state.yaw_deg))
        pitch_error = abs(desired_pitch - self.state.pitch_deg)
        return max(yaw_error, pitch_error) <= self.config.fire_arc_deg

    def _active_projectile_speed(self) -> float:
        if self.config.ammunition_types:
            ammo = None
            if self.config.default_ammunition:
                for candidate in self.config.ammunition_types:
                    if candidate.name == self.config.default_ammunition:
                        ammo = candidate
                        break
            if ammo is None:
                ammo = self.config.ammunition_types[0]
            return ammo.projectile_speed
        return self.config.projectile_speed

    def _check_obstruction(self, target: Target) -> Optional[ObstructionSample]:
        if not self.config.obstruction_check:
            return None

        result = self.config.obstruction_check(self.position, target.position)
        sample: ObstructionSample
        if isinstance(result, ObstructionSample):
            sample = result
        elif isinstance(result, bool):
            sample = ObstructionSample(blocked=not result)
        elif result is None:
            sample = ObstructionSample(blocked=False)
        else:
            sample = ObstructionSample(blocked=bool(result))
        if self.config.obstruction_feedback:
            self.config.obstruction_feedback(sample)
        return sample

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        return (angle + 180.0) % 360.0 - 180.0

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _find_matching_target(targets: Sequence[Target], target_id: str) -> Optional[Target]:
        for target in targets:
            if target.id == target_id:
                return target
        return None
