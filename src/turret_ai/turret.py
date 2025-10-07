"""Core AI turret implementation inspired by STS 3D behaviour."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Callable, Iterable, List, Optional, Sequence, Union
from typing import Iterable, List, Optional, Sequence

from .geometry import Vector3, UP, solve_intercept_time


@dataclass(frozen=True)
class AmmunitionType:
    """Defines the characteristics of a projectile fired by the turret."""

    name: str
    projectile_speed: float
    damage: float
    heat_per_shot: float = 1.0


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
    ammunition_types: Sequence[AmmunitionType] = field(default_factory=tuple)
    default_ammunition: Optional[str] = None
    obstruction_check: Optional[
        Callable[[Vector3, Vector3], Union[bool, "ObstructionSample"]]
    ] = None
    heat_capacity: float = 12.0
    overheat_threshold: float = 9.0
    heat_resume_threshold: float = 4.0
    heat_dissipation_rate: float = 3.0
    idle_scan_speed_deg: float = 25.0
    idle_scan_yaw_range_deg: float = 45.0
    idle_scan_pitch_deg: float = 6.0
    heat_feedback: Optional[Callable[[float, float, bool], None]] = None
    power_capacity: float = 0.0
    power_per_shot: float = 0.0
    power_recharge_rate: float = 0.0
    power_feedback: Optional[Callable[[float, float], None]] = None


@dataclass(frozen=True)
class ObstructionSample:
    """Result data from the obstruction callback for complex environments."""

    blocked: bool
    hit_position: Optional[Vector3] = None
    surface_normal: Optional[Vector3] = None
    navigation_cost: float = 0.0


@dataclass
class ManualWaypoint:
    """Queued manual override orientation with scripted burst behaviour."""

    yaw_deg: float
    pitch_deg: float
    dwell_time: float = 0.5
    fire_burst: int = 0
    burst_interval: float = 0.1


@dataclass
class TurretState:
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    cooldown: float = 0.0
    tracked_target: Optional[Target] = None
    time_since_seen: float = 0.0
    last_prediction_time: float = 0.0
    current_ammunition: Optional[AmmunitionType] = None
    heat: float = 0.0
    overheated: bool = False
    idle_time: float = 0.0
    manual_override: bool = False
    manual_yaw_deg: float = 0.0
    manual_pitch_deg: float = 0.0
    manual_fire_request: bool = False
    manual_waypoints: List[ManualWaypoint] = field(default_factory=list)
    manual_waypoint_timer: float = 0.0
    manual_burst_shots_remaining: int = 0
    manual_burst_cooldown: float = 0.0
    manual_burst_interval: float = 0.0
    power: float = 0.0
    last_obstruction: Optional[ObstructionSample] = None


@dataclass
class Turret:
    """Stateful AI turret controller."""

    position: Vector3
    config: TurretConfig = field(default_factory=TurretConfig)
    state: TurretState = field(default_factory=TurretState)

    def __post_init__(self) -> None:
        ammo_types = list(self.config.ammunition_types)
        if not ammo_types:
            ammo_types.append(
                AmmunitionType(
                    name="standard",
                    projectile_speed=self.config.projectile_speed,
                    damage=10.0,
                    heat_per_shot=1.0,
                )
            )
            self.config.ammunition_types = tuple(ammo_types)

        selected = self._resolve_ammunition(self.config.default_ammunition)
        self.state.current_ammunition = selected
        if self.config.power_capacity > 0:
            self.state.power = self.config.power_capacity

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

    def _compute_desired_angles(
        self, position: Vector3, projectile_speed: float
    ) -> tuple[float, float, float]:
    def _compute_desired_angles(self, position: Vector3) -> tuple[float, float, float]:
        """Return desired yaw, pitch (in degrees) and time to impact."""
        offset = position - self.position
        distance = offset.magnitude()
        if distance == 0:
            return self.state.yaw_deg, self.state.pitch_deg, 0.0

        yaw_rad = math.atan2(offset.x, offset.z)
        pitch_rad = math.asin(max(-1.0, min(1.0, offset.y / distance)))
        time_to_target = distance / projectile_speed if projectile_speed else 0.0
        return math.degrees(yaw_rad), math.degrees(pitch_rad), time_to_target

    def _predict_intercept(self, target: Target, projectile_speed: float) -> tuple[Vector3, float]:
        time_to_target = distance / self.config.projectile_speed if self.config.projectile_speed else 0.0
        return math.degrees(yaw_rad), math.degrees(pitch_rad), time_to_target

    def _predict_intercept(self, target: Target) -> tuple[Vector3, float]:
        intercept_time = solve_intercept_time(
            origin=self.position,
            target_position=target.position,
            target_velocity=target.velocity,
            projectile_speed=projectile_speed,
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
        previous_heat = state.heat
        state.cooldown = max(0.0, state.cooldown - dt)
        state.heat = max(0.0, state.heat - self.config.heat_dissipation_rate * dt)
        if not math.isclose(previous_heat, state.heat):
            self._notify_heat_feedback()
        cooled_this_tick = False
        if state.overheated and state.heat <= self.config.heat_resume_threshold:
            state.overheated = False
            cooled_this_tick = True
            self._notify_heat_feedback()
        if self.config.power_capacity > 0:
            previous_power = state.power
            state.power = min(
                self.config.power_capacity,
                state.power + self.config.power_recharge_rate * dt,
            )
            if self.config.power_feedback and not math.isclose(previous_power, state.power):
                self.config.power_feedback(state.power, self.config.power_capacity)
        targets_list = list(targets)

        if state.manual_override:
            state.tracked_target = None
            state.time_since_seen = 0.0
            state.last_prediction_time = 0.0
            manual_result = self._update_manual_override(dt, cooled_this_tick)
            if manual_result:
                return manual_result
            return None

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
            self._perform_idle_scan(dt)
            state.last_prediction_time = 0.0
            return None

        projectile_speed = self.current_ammunition.projectile_speed
        predicted_position, intercept_time = self._predict_intercept(
            state.tracked_target, projectile_speed
        )
        state.last_prediction_time = intercept_time
        yaw_deg, pitch_deg, _ = self._compute_desired_angles(
            predicted_position, projectile_speed
        )
            return None

        predicted_position, intercept_time = self._predict_intercept(state.tracked_target)
        state.last_prediction_time = intercept_time
        yaw_deg, pitch_deg, _ = self._compute_desired_angles(predicted_position)
        yaw_deg, pitch_deg = self._clamp_angles(yaw_deg, pitch_deg)

        # Smooth rotation towards desired angles
        state.yaw_deg = self._approach_angle(state.yaw_deg, yaw_deg, self.config.max_turn_rate_deg * dt)
        state.pitch_deg = self._approach_angle(state.pitch_deg, pitch_deg, self.config.max_turn_rate_deg * dt)

        if state.cooldown > 0 or state.overheated:
            return None

        if self._is_aligned(state.yaw_deg, yaw_deg) and self._is_aligned(state.pitch_deg, pitch_deg):
            if self.config.obstruction_check:
                sample = self._coerce_obstruction_result(
                    self.config.obstruction_check(self.position, predicted_position)
                )
                state.last_obstruction = sample
                if sample.blocked:
                    return None
            if cooled_this_tick:
                return None
            if not self._consume_power():
                return None
            state.cooldown = self.config.fire_cooldown
            fired_id = state.tracked_target.id
            self._apply_heat()
            return fired_id
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

    @property
    def current_ammunition(self) -> AmmunitionType:
        current = self.state.current_ammunition
        if current is None:
            current = self._resolve_ammunition(self.config.default_ammunition)
            self.state.current_ammunition = current
        return current

    def set_ammunition(self, name: str) -> AmmunitionType:
        ammunition = self._resolve_ammunition(name)
        self.state.current_ammunition = ammunition
        return ammunition

    def cycle_ammunition(self) -> AmmunitionType:
        ammo_list = list(self.config.ammunition_types)
        current = self.current_ammunition
        try:
            index = next(i for i, ammo in enumerate(ammo_list) if ammo.name == current.name)
        except StopIteration:
            index = -1
        next_ammo = ammo_list[(index + 1) % len(ammo_list)]
        self.state.current_ammunition = next_ammo
        return next_ammo

    def engage_manual_override(
        self,
        yaw_deg: float,
        pitch_deg: float,
        *,
        waypoints: Optional[Iterable[ManualWaypoint]] = None,
    ) -> None:
        yaw, pitch = self._clamp_angles(yaw_deg, pitch_deg)
        self.state.manual_override = True
        self.state.manual_yaw_deg = yaw
        self.state.manual_pitch_deg = pitch
        self.state.manual_waypoints = list(waypoints or [])
        self.state.manual_waypoint_timer = 0.0
        self.state.manual_burst_shots_remaining = 0
        self.state.manual_burst_cooldown = 0.0
        self.state.manual_burst_interval = 0.0

    def clear_manual_override(self) -> None:
        self.state.manual_override = False
        self.state.manual_fire_request = False
        self.state.manual_waypoints.clear()
        self.state.manual_waypoint_timer = 0.0
        self.state.manual_burst_shots_remaining = 0
        self.state.manual_burst_cooldown = 0.0
        self.state.manual_burst_interval = 0.0

    def request_manual_fire(self) -> None:
        self.state.manual_fire_request = True

    def queue_manual_waypoint(self, waypoint: ManualWaypoint) -> None:
        self.state.manual_waypoints.append(waypoint)

    def _apply_manual_orientation(self, dt: float) -> None:
        state = self.state
        yaw_speed = self.config.max_turn_rate_deg * dt
        state.yaw_deg = self._approach_angle(state.yaw_deg, state.manual_yaw_deg, yaw_speed)
        state.pitch_deg = self._approach_angle(
            state.pitch_deg,
            max(self.config.min_elevation_deg, min(self.config.max_elevation_deg, state.manual_pitch_deg)),
            yaw_speed,
        )

    def _perform_idle_scan(self, dt: float) -> None:
        state = self.state
        state.idle_time += dt
        phase = state.idle_time * math.radians(self.config.idle_scan_speed_deg)
        desired_yaw = math.sin(phase) * self.config.idle_scan_yaw_range_deg
        desired_pitch = math.sin(phase * 0.5) * self.config.idle_scan_pitch_deg
        yaw_speed = self.config.max_turn_rate_deg * dt
        state.yaw_deg = self._approach_angle(state.yaw_deg, desired_yaw, yaw_speed)
        state.pitch_deg = self._approach_angle(state.pitch_deg, desired_pitch, yaw_speed)

    def _apply_heat(self) -> None:
        state = self.state
        ammo = self.current_ammunition
        state.heat = min(self.config.heat_capacity, state.heat + ammo.heat_per_shot)
        if state.heat >= self.config.overheat_threshold:
            state.overheated = True
        self._notify_heat_feedback()

    def _resolve_ammunition(self, name: Optional[str]) -> AmmunitionType:
        ammo_list = list(self.config.ammunition_types)
        if not ammo_list:
            raise ValueError("TurretConfig.ammunition_types must contain at least one ammunition type")

        if name is None:
            return ammo_list[0]

        for ammo in ammo_list:
            if ammo.name == name:
                return ammo
        raise ValueError(f"Unknown ammunition type '{name}'")

    def _notify_heat_feedback(self) -> None:
        if self.config.heat_feedback:
            self.config.heat_feedback(
                self.state.heat,
                self.config.heat_capacity,
                self.state.overheated,
            )

    def _consume_power(self) -> bool:
        if self.config.power_capacity <= 0 or self.config.power_per_shot <= 0:
            return True
        if self.state.power + 1e-6 < self.config.power_per_shot:
            return False
        self.state.power -= self.config.power_per_shot
        if self.config.power_feedback:
            self.config.power_feedback(self.state.power, self.config.power_capacity)
        return True

    def _coerce_obstruction_result(
        self, result: Union[bool, ObstructionSample]
    ) -> ObstructionSample:
        if isinstance(result, ObstructionSample):
            return result
        return ObstructionSample(blocked=not result)

    def _update_manual_override(self, dt: float, cooled_this_tick: bool) -> Optional[str]:
        state = self.state
        if state.manual_waypoints:
            current = state.manual_waypoints[0]
            yaw, pitch = self._clamp_angles(current.yaw_deg, current.pitch_deg)
            state.manual_yaw_deg = yaw
            state.manual_pitch_deg = pitch
            if self._is_aligned(state.yaw_deg, yaw) and self._is_aligned(state.pitch_deg, pitch):
                state.manual_waypoint_timer += dt
                if current.fire_burst > 0 and state.manual_burst_shots_remaining == 0:
                    state.manual_burst_shots_remaining = current.fire_burst
                    state.manual_burst_interval = current.burst_interval
                    state.manual_burst_cooldown = 0.0
                if state.manual_waypoint_timer >= current.dwell_time:
                    state.manual_waypoint_timer = 0.0
                    state.manual_waypoints.pop(0)
                    state.manual_burst_shots_remaining = 0
                    state.manual_burst_cooldown = 0.0
                    state.manual_burst_interval = 0.0
            else:
                state.manual_waypoint_timer = 0.0
        self._apply_manual_orientation(dt)
        state.manual_burst_cooldown = max(0.0, state.manual_burst_cooldown - dt)
        if state.cooldown > 0 or state.overheated or cooled_this_tick:
            state.manual_fire_request = False
            return None
        if state.manual_fire_request and self._is_aligned(state.yaw_deg, state.manual_yaw_deg) and self._is_aligned(state.pitch_deg, state.manual_pitch_deg):
            if not self._consume_power():
                state.manual_fire_request = False
                return None
            state.manual_fire_request = False
            self._apply_heat()
            state.cooldown = self.config.fire_cooldown
            return "manual_override"
        state.manual_fire_request = False
        if (
            state.manual_burst_shots_remaining > 0
            and state.manual_burst_cooldown <= 0
            and self._is_aligned(state.yaw_deg, state.manual_yaw_deg)
            and self._is_aligned(state.pitch_deg, state.manual_pitch_deg)
        ):
            if not self._consume_power():
                return None
            state.manual_burst_shots_remaining -= 1
            state.manual_burst_cooldown = state.manual_burst_interval
            self._apply_heat()
            state.cooldown = self.config.fire_cooldown
            return "manual_override_burst"
        return None


__all__ = [
    "AmmunitionType",

__all__ = [
    "Target",
    "Turret",
    "TurretConfig",
    "TurretState",
    "ManualWaypoint",
    "ObstructionSample",
    "Vector3",
    "UP",
]

