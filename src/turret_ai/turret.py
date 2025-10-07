"""Core AI turret implementation inspired by STS 3D behaviour."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable, List, Optional, Sequence

from .geometry import Vector3, UP, solve_intercept_time


@dataclass
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
    detection_radius: float = 50.0
    target_memory: float = 1.5  # seconds before forgetting lost targets
    max_prediction_time: float = 3.0
    fire_cooldown: float = 0.2


@dataclass
class TurretState:
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    cooldown: float = 0.0
    tracked_target: Optional[Target] = None
    time_since_seen: float = 0.0
    last_prediction_time: float = 0.0


@dataclass
class Turret:
    """Stateful AI turret controller."""

    position: Vector3
    config: TurretConfig = field(default_factory=TurretConfig)
    state: TurretState = field(default_factory=TurretState)

    def select_target(self, candidates: Iterable[Target]) -> Optional[Target]:
        """Pick the highest priority target inside detection radius."""
        in_range: List[Target] = []
        for target in candidates:
            distance = self.position.distance_to(target.position)
            if distance <= self.config.detection_radius:
                in_range.append(target)

        if not in_range:
            return None

        def sort_key(t: Target) -> tuple[int, float]:
            # Higher priority first, closer distance preferred
            return (-t.priority, self.position.distance_to(t.position))

        return min(in_range, key=sort_key)

    def _clamp_angles(self, yaw: float, pitch: float) -> tuple[float, float]:
        pitch = max(self.config.min_elevation_deg, min(self.config.max_elevation_deg, pitch))
        yaw = (yaw + 180.0) % 360.0 - 180.0
        return yaw, pitch

    def _compute_desired_angles(self, position: Vector3) -> tuple[float, float, float]:
        """Return desired yaw, pitch (in degrees) and time to impact."""
        offset = position - self.position
        distance = offset.magnitude()
        if distance == 0:
            return self.state.yaw_deg, self.state.pitch_deg, 0.0

        yaw_rad = math.atan2(offset.x, offset.z)
        pitch_rad = math.asin(max(-1.0, min(1.0, offset.y / distance)))
        time_to_target = distance / self.config.projectile_speed if self.config.projectile_speed else 0.0
        return math.degrees(yaw_rad), math.degrees(pitch_rad), time_to_target

    def _predict_intercept(self, target: Target) -> tuple[Vector3, float]:
        intercept_time = solve_intercept_time(
            origin=self.position,
            target_position=target.position,
            target_velocity=target.velocity,
            projectile_speed=self.config.projectile_speed,
            max_time=self.config.max_prediction_time,
        )
        predicted_position = target.predict_position(intercept_time)
        return predicted_position, intercept_time

    @staticmethod
    def _find_matching_target(targets: Sequence[Target], target_id: str) -> Optional[Target]:
        for candidate in targets:
            if candidate.id == target_id:
                return candidate
        return None

    def update(self, dt: float, targets: Iterable[Target]) -> Optional[str]:
        """Advance simulation and return target id if fired."""
        state = self.state
        state.cooldown = max(0.0, state.cooldown - dt)
        targets_list = list(targets)

        # Maintain current target if still valid
        if state.tracked_target:
            updated = self._find_matching_target(targets_list, state.tracked_target.id)
            if updated:
                state.tracked_target = updated
                distance = self.position.distance_to(updated.position)
                if distance <= self.config.detection_radius:
                    state.time_since_seen = 0.0
                else:
                    state.time_since_seen += dt
            else:
                state.time_since_seen += dt
            if state.time_since_seen > self.config.target_memory:
                state.tracked_target = None

        if state.tracked_target is None:
            state.tracked_target = self.select_target(targets_list)
            if state.tracked_target:
                state.time_since_seen = 0.0

        if state.tracked_target is None:
            return None

        predicted_position, intercept_time = self._predict_intercept(state.tracked_target)
        state.last_prediction_time = intercept_time
        yaw_deg, pitch_deg, _ = self._compute_desired_angles(predicted_position)
        yaw_deg, pitch_deg = self._clamp_angles(yaw_deg, pitch_deg)

        # Smooth rotation towards desired angles
        state.yaw_deg = self._approach_angle(state.yaw_deg, yaw_deg, self.config.max_turn_rate_deg * dt)
        state.pitch_deg = self._approach_angle(state.pitch_deg, pitch_deg, self.config.max_turn_rate_deg * dt)

        if state.cooldown > 0:
            return None

        if self._is_aligned(state.yaw_deg, yaw_deg) and self._is_aligned(state.pitch_deg, pitch_deg):
            state.cooldown = self.config.fire_cooldown
            return state.tracked_target.id

        return None

    @staticmethod
    def _approach_angle(current: float, target: float, max_delta: float) -> float:
        delta = (target - current + 180.0) % 360.0 - 180.0
        delta = max(-max_delta, min(max_delta, delta))
        return (current + delta + 180.0) % 360.0 - 180.0

    def _is_aligned(self, current: float, target: float) -> bool:
        delta = abs((target - current + 180.0) % 360.0 - 180.0)
        return delta <= self.config.fire_arc_deg


__all__ = [
    "Target",
    "Turret",
    "TurretConfig",
    "TurretState",
    "Vector3",
    "UP",
]

