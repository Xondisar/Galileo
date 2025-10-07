"""Core AI turret implementation inspired by STS 3D behaviour."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import (
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)
from typing import TYPE_CHECKING

from .geometry import Vector3, UP, solve_intercept_time

if TYPE_CHECKING:  # pragma: no cover - used only for type checking
    from .exporters import TelemetryExporter


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
    obstruction_feedback: Optional[Callable[["ObstructionSample"], None]] = None
    orientation_blend: Optional[Callable[[float, float], Tuple[float, float]]] = None
    cooperative_threat_weight: float = 1.0
    cooperative_latency_decay: float = 0.5
    cooperative_confidence_exponent: float = 1.0
    telemetry_callback: Optional[Callable[["TurretTelemetry"], None]] = None
    effects_callback: Optional[Callable[["TurretTelemetry"], None]] = None
    rl_training_callback: Optional[
        Callable[["TurretTelemetry", Dict[str, float]], None]
    ] = None
    telemetry_exporter: Optional["TelemetryExporter"] = None
    telemetry_capture_callback: Optional[
        Callable[["TurretTelemetry", int], None]
    ] = None
    rl_reward_target: float = 0.0
    rl_reward_adjust_rate: float = 0.05
    rl_reward_smoothing: float = 0.2
    rl_cooldown_bounds: Tuple[float, float] = (0.5, 1.5)
    rl_threat_bias_bounds: Tuple[float, float] = (0.5, 2.0)


@dataclass(frozen=True)
class ObstructionSample:
    """Result data from the obstruction callback for complex environments."""

    blocked: bool
    hit_position: Optional[Vector3] = None
    surface_normal: Optional[Vector3] = None
    navigation_cost: float = 0.0


@dataclass
class TargetDesignation:
    """Threat data shared by allied sensors."""

    target_id: str
    threat: float
    ttl: float = 2.0
    sensor_id: Optional[str] = None
    sensor_kind: str = "generic"
    decay_rate: Optional[float] = None
    confidence: float = 1.0
    latency: float = 0.0


@dataclass
class _SensorContribution:
    threat: float
    time_remaining: float
    decay_rate: float
    sensor_kind: str
    confidence: float
    confidence_weight: float
    latency: float
    latency_weight: float

    def decay(self, dt: float) -> None:
        self.time_remaining -= dt
        self.threat = max(0.0, self.threat - self.decay_rate * dt)

    @property
    def expired(self) -> bool:
        return self.time_remaining <= 0.0 or self.threat <= 1e-3

    def effective_threat(self) -> float:
        return max(0.0, self.threat) * self.confidence_weight * self.latency_weight


@dataclass
class _AggregatedDesignation:
    contributions: Dict[str, _SensorContribution] = field(default_factory=dict)

    def total_threat(self) -> float:
        return sum(
            contribution.effective_threat()
            for contribution in self.contributions.values()
        )

    def sensor_breakdown(self) -> Dict[str, float]:
        breakdown: Dict[str, float] = {}
        for contribution in self.contributions.values():
            effective = contribution.effective_threat()
            if effective <= 0:
                continue
            breakdown[contribution.sensor_kind] = breakdown.get(
                contribution.sensor_kind, 0.0
            ) + effective
        return breakdown


@dataclass(frozen=True)
class TurretTelemetry:
    """Snapshot of the turret state for external dashboards."""

    time: float
    yaw_deg: float
    pitch_deg: float
    heat: float
    overheated: bool
    power: float
    power_capacity: float
    tracked_target: Optional[str]
    prediction_time: float
    ammunition: Optional[str]
    cooldown: float
    fired_target: Optional[str]
    manual_override: bool
    obstruction: Optional[ObstructionSample]
    cooperative_designation_count: int
    cooperative_threat_score: float
    cooperative_sensor_breakdown: Dict[str, float] = field(default_factory=dict)
    cooperative_average_confidence: float = 0.0
    cooperative_average_latency: float = 0.0


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
    cooperative_designations: Dict[str, _AggregatedDesignation] = field(
        default_factory=dict
    )
    designation_sequence: int = 0
    total_time: float = 0.0
    rl_cooldown_scale: float = 1.0
    rl_threat_bias: float = 1.0
    rl_reward_trace: float = 0.0
    capture_frame_index: int = 0


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
        cd_min, cd_max = self.config.rl_cooldown_bounds
        bias_min, bias_max = self.config.rl_threat_bias_bounds
        self.state.rl_cooldown_scale = self._clamp_value(1.0, cd_min, cd_max)
        self.state.rl_threat_bias = self._clamp_value(1.0, bias_min, bias_max)
        self.state.rl_reward_trace = self.config.rl_reward_target

    def select_target(self, candidates: Iterable[Target]) -> Optional[Target]:
        """Pick the highest priority target inside detection radius."""
        in_range: List[Target] = []
        for target in candidates:
            distance = self.position.distance_to(target.position)
            if distance <= self.config.detection_radius:
                in_range.append(target)

        if not in_range:
            return None

        def sort_key(t: Target) -> tuple[float, float]:
            designation = self.state.cooperative_designations.get(t.id)
            threat = designation.total_threat() if designation else 0.0
            score = t.priority + (
                self.config.cooperative_threat_weight
                * self.state.rl_threat_bias
                * threat
            )
            # Higher score first, closer distance preferred
            return (-score, self.position.distance_to(t.position))

        return min(in_range, key=sort_key)

    def _clamp_angles(self, yaw: float, pitch: float) -> tuple[float, float]:
        pitch = max(self.config.min_elevation_deg, min(self.config.max_elevation_deg, pitch))
        yaw = (yaw + 180.0) % 360.0 - 180.0
        return yaw, pitch

    @staticmethod
    def _clamp_value(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))

    def _compute_desired_angles(
        self, position: Vector3, projectile_speed: float
    ) -> tuple[float, float, float]:
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
        intercept_time = solve_intercept_time(
            origin=self.position,
            target_position=target.position,
            target_velocity=target.velocity,
            projectile_speed=projectile_speed,
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
        state.total_time += dt
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

        self._decay_designations(dt)
        targets_list = list(targets)

        if state.manual_override:
            state.tracked_target = None
            state.time_since_seen = 0.0
            state.last_prediction_time = 0.0
            manual_result = self._update_manual_override(dt, cooled_this_tick)
            self._emit_telemetry(manual_result)
            return manual_result

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
            self._emit_telemetry(None)
            return None

        projectile_speed = self.current_ammunition.projectile_speed
        predicted_position, intercept_time = self._predict_intercept(
            state.tracked_target, projectile_speed
        )
        state.last_prediction_time = intercept_time
        yaw_deg, pitch_deg, _ = self._compute_desired_angles(
            predicted_position, projectile_speed
        )
        yaw_deg, pitch_deg = self._clamp_angles(yaw_deg, pitch_deg)

        # Smooth rotation towards desired angles
        state.yaw_deg = self._approach_angle(
            state.yaw_deg, yaw_deg, self.config.max_turn_rate_deg * dt
        )
        state.pitch_deg = self._approach_angle(
            state.pitch_deg, pitch_deg, self.config.max_turn_rate_deg * dt
        )
        state.yaw_deg, state.pitch_deg = self._apply_orientation_blend(
            state.yaw_deg, state.pitch_deg
        )

        if state.cooldown > 0 or state.overheated:
            self._emit_telemetry(None)
            return None

        if self._is_aligned(state.yaw_deg, yaw_deg) and self._is_aligned(state.pitch_deg, pitch_deg):
            if self.config.obstruction_check:
                sample = self._coerce_obstruction_result(
                    self.config.obstruction_check(self.position, predicted_position)
                )
                state.last_obstruction = sample
                self._notify_obstruction_feedback(sample)
                if sample.blocked:
                    self._emit_telemetry(None)
                    return None
            if cooled_this_tick:
                self._emit_telemetry(None)
                return None
            if not self._consume_power():
                self._emit_telemetry(None)
                return None
            state.cooldown = self._current_fire_cooldown()
            fired_id = state.tracked_target.id
            self._apply_heat()
            self._emit_telemetry(fired_id)
            return fired_id

        self._emit_telemetry(None)
        return None

    @staticmethod
    def _approach_angle(current: float, target: float, max_delta: float) -> float:
        delta = (target - current + 180.0) % 360.0 - 180.0
        delta = max(-max_delta, min(max_delta, delta))
        return (current + delta + 180.0) % 360.0 - 180.0

    def _is_aligned(self, current: float, target: float) -> bool:
        delta = abs((target - current + 180.0) % 360.0 - 180.0)
        return delta <= self.config.fire_arc_deg

    def _current_fire_cooldown(self) -> float:
        base = self.config.fire_cooldown
        if base <= 0:
            return 0.0
        scale = max(0.0, self.state.rl_cooldown_scale)
        cooldown = base * scale
        return max(0.01, cooldown)

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
        state.yaw_deg, state.pitch_deg = self._apply_orientation_blend(
            state.yaw_deg, state.pitch_deg
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
        state.yaw_deg, state.pitch_deg = self._apply_orientation_blend(
            state.yaw_deg, state.pitch_deg
        )

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
            state.cooldown = self._current_fire_cooldown()
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
            state.cooldown = self._current_fire_cooldown()
            return "manual_override_burst"
        return None

    def ingest_designations(self, designations: Iterable[TargetDesignation]) -> None:
        """Accept cooperative target designations from allied sensors."""

        for designation in designations:
            if designation.threat <= 0 or designation.ttl <= 0:
                continue
            container = self.state.cooperative_designations.setdefault(
                designation.target_id, _AggregatedDesignation()
            )
            sensor_key = designation.sensor_id
            if sensor_key is None:
                sensor_key = f"sensor-{self.state.designation_sequence}"
                self.state.designation_sequence += 1
            confidence = max(0.0, min(1.0, designation.confidence))
            exponent = max(1e-3, self.config.cooperative_confidence_exponent)
            confidence_weight = confidence ** exponent
            latency = max(0.0, designation.latency)
            decay_factor = max(0.0, self.config.cooperative_latency_decay)
            latency_weight = math.exp(-latency * decay_factor) if decay_factor > 0 else 1.0
            if confidence_weight <= 0 or latency_weight <= 0:
                continue
            ttl = max(1e-3, designation.ttl - latency)
            decay_rate = designation.decay_rate
            if decay_rate is None:
                decay_rate = designation.threat / ttl
            container.contributions[sensor_key] = _SensorContribution(
                threat=designation.threat,
                time_remaining=ttl,
                decay_rate=decay_rate,
                sensor_kind=designation.sensor_kind,
                confidence=confidence,
                confidence_weight=confidence_weight,
                latency=latency,
                latency_weight=latency_weight,
            )

    def _decay_designations(self, dt: float) -> None:
        if not self.state.cooperative_designations:
            return
        expired_targets: List[str] = []
        for target_id, designation in self.state.cooperative_designations.items():
            expired_contributors: List[str] = []
            for sensor_id, contribution in designation.contributions.items():
                contribution.decay(dt)
                if contribution.expired:
                    expired_contributors.append(sensor_id)
            for sensor_id in expired_contributors:
                designation.contributions.pop(sensor_id, None)
            if not designation.contributions:
                expired_targets.append(target_id)
        for target_id in expired_targets:
            self.state.cooperative_designations.pop(target_id, None)

    def _apply_orientation_blend(self, yaw: float, pitch: float) -> tuple[float, float]:
        if not self.config.orientation_blend:
            return yaw, pitch
        blended_yaw, blended_pitch = self.config.orientation_blend(yaw, pitch)
        return self._clamp_angles(blended_yaw, blended_pitch)

    def _notify_obstruction_feedback(self, sample: ObstructionSample) -> None:
        if self.config.obstruction_feedback:
            self.config.obstruction_feedback(sample)

    def _emit_telemetry(self, fired_target: Optional[str]) -> None:
        if (
            not self.config.telemetry_callback
            and not self.config.telemetry_exporter
            and not self.config.effects_callback
            and not self.config.rl_training_callback
            and not self.config.telemetry_capture_callback
        ):
            return
        (
            total_threat,
            sensor_breakdown,
            contribution_count,
            avg_confidence,
            avg_latency,
        ) = self._gather_designation_stats()
        telemetry = TurretTelemetry(
            time=self.state.total_time,
            yaw_deg=self.state.yaw_deg,
            pitch_deg=self.state.pitch_deg,
            heat=self.state.heat,
            overheated=self.state.overheated,
            power=self.state.power,
            power_capacity=self.config.power_capacity,
            tracked_target=self.state.tracked_target.id if self.state.tracked_target else None,
            prediction_time=self.state.last_prediction_time,
            ammunition=self.state.current_ammunition.name if self.state.current_ammunition else None,
            cooldown=self.state.cooldown,
            fired_target=fired_target,
            manual_override=self.state.manual_override,
            obstruction=self.state.last_obstruction,
            cooperative_designation_count=contribution_count,
            cooperative_threat_score=total_threat,
            cooperative_sensor_breakdown=sensor_breakdown,
            cooperative_average_confidence=avg_confidence,
            cooperative_average_latency=avg_latency,
        )
        if self.config.telemetry_callback:
            self.config.telemetry_callback(telemetry)
        if self.config.telemetry_exporter:
            self.config.telemetry_exporter.send(telemetry)
        if self.config.effects_callback and (
            telemetry.fired_target or telemetry.obstruction is not None
        ):
            self.config.effects_callback(telemetry)
        rl_reward = None
        if self.config.rl_training_callback:
            rl_reward = self.config.rl_training_callback(
                telemetry, self._build_rl_feature_vector(telemetry)
            )
        if rl_reward is not None:
            try:
                reward_value = float(rl_reward)
            except (TypeError, ValueError):
                reward_value = None
            else:
                if math.isfinite(reward_value):
                    self.apply_rl_reward(reward_value)
        if self.config.telemetry_capture_callback:
            self.config.telemetry_capture_callback(
                telemetry, self.state.capture_frame_index
            )
        self.state.capture_frame_index += 1

    def _gather_designation_stats(
        self,
    ) -> tuple[float, Dict[str, float], int, float, float]:
        total = 0.0
        breakdown: Dict[str, float] = {}
        contribution_count = 0
        confidence_weight = 0.0
        latency_weight = 0.0
        for designation in self.state.cooperative_designations.values():
            for contribution in designation.contributions.values():
                effective = contribution.effective_threat()
                if effective <= 0:
                    continue
                total += effective
                contribution_count += 1
                breakdown[contribution.sensor_kind] = breakdown.get(
                    contribution.sensor_kind, 0.0
                ) + effective
                confidence_weight += contribution.confidence * effective
                latency_weight += contribution.latency * effective
        avg_confidence = confidence_weight / total if total > 1e-6 else 0.0
        avg_latency = latency_weight / total if total > 1e-6 else 0.0
        return total, breakdown, contribution_count, avg_confidence, avg_latency

    def _build_rl_feature_vector(self, telemetry: TurretTelemetry) -> Dict[str, float]:
        ammo = self.state.current_ammunition
        heat_ratio = 0.0
        if self.config.heat_capacity > 0:
            heat_ratio = telemetry.heat / self.config.heat_capacity
        power_ratio = 0.0
        if telemetry.power_capacity > 0:
            power_ratio = telemetry.power / telemetry.power_capacity
        feature_vector: Dict[str, float] = {
            "heat_ratio": heat_ratio,
            "power_ratio": power_ratio,
            "cooldown": telemetry.cooldown,
            "cooperative_threat": telemetry.cooperative_threat_score,
            "manual_override": 1.0 if telemetry.manual_override else 0.0,
            "overheated": 1.0 if telemetry.overheated else 0.0,
            "rl_cooldown_scale": self.state.rl_cooldown_scale,
            "rl_threat_bias": self.state.rl_threat_bias,
            "coop_confidence": telemetry.cooperative_average_confidence,
            "coop_latency": telemetry.cooperative_average_latency,
        }
        if ammo is not None:
            feature_vector.update(
                {
                    "ammo_damage": ammo.damage,
                    "ammo_heat": ammo.heat_per_shot,
                    "ammo_speed": ammo.projectile_speed,
                }
            )
        return feature_vector

    def apply_rl_reward(self, reward: float) -> None:
        if not math.isfinite(reward):
            return
        smoothing = max(0.0, min(1.0, self.config.rl_reward_smoothing))
        if smoothing <= 0 or self.state.total_time <= 0:
            self.state.rl_reward_trace = reward
        else:
            self.state.rl_reward_trace = (
                (1.0 - smoothing) * self.state.rl_reward_trace
                + smoothing * reward
            )
        adjust = self.config.rl_reward_adjust_rate
        if adjust <= 0:
            return
        delta = self.state.rl_reward_trace - self.config.rl_reward_target
        cd_min, cd_max = self.config.rl_cooldown_bounds
        threat_min, threat_max = self.config.rl_threat_bias_bounds
        self.state.rl_cooldown_scale = self._clamp_value(
            self.state.rl_cooldown_scale - delta * adjust, cd_min, cd_max
        )
        self.state.rl_threat_bias = self._clamp_value(
            self.state.rl_threat_bias + delta * adjust, threat_min, threat_max
        )


__all__ = [
    "AmmunitionType",
    "Target",
    "Turret",
    "TurretConfig",
    "TurretState",
    "ManualWaypoint",
    "ObstructionSample",
    "TargetDesignation",
    "TurretTelemetry",
    "Vector3",
    "UP",
]

