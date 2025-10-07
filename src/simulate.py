from __future__ import annotations

"""Run a small command line simulation showcasing the turret AI."""

import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.turret_ai.geometry import Vector3
from src.turret_ai.exporters import (
    CaptureOverlayTelemetryExporter,
    RpcTelemetryExporter,
)
from src.turret_ai.turret import (
    AmmunitionType,
    ManualWaypoint,
    ObstructionSample,
    TargetDesignation,
    Target,
    Turret,
    TurretConfig,
    TurretTelemetry,
)


@dataclass
class SimulationTarget:
    target: Target
    acceleration: Vector3


class MultiTelemetryExporter:
    def __init__(self, *exporters) -> None:
        self._exporters = exporters

    def send(self, telemetry: TurretTelemetry) -> None:
        for exporter in self._exporters:
            exporter.send(telemetry)

    def close(self) -> None:
        for exporter in self._exporters:
            exporter.close()


class TurretSimulation:
    def __init__(self, seed: int = 42) -> None:
        random.seed(seed)
        ammo_types = (
            AmmunitionType("standard", projectile_speed=55.0, damage=10.0, heat_per_shot=1.2),
            AmmunitionType("piercing", projectile_speed=70.0, damage=14.0, heat_per_shot=1.8),
            AmmunitionType("rapid", projectile_speed=45.0, damage=6.0, heat_per_shot=0.8),
        )
        rpc_exporter = RpcTelemetryExporter(self._dispatch_rpc, method="turret.telemetry")
        capture_exporter = CaptureOverlayTelemetryExporter(self._record_capture_stream)
        exporter = MultiTelemetryExporter(rpc_exporter, capture_exporter)
        config = TurretConfig(
            max_turn_rate_deg=240.0,
            fire_arc_deg=4.0,
            detection_radius=60.0,
            ammunition_types=ammo_types,
            default_ammunition="standard",
            heat_capacity=10.0,
            overheat_threshold=7.5,
            heat_resume_threshold=3.0,
            heat_dissipation_rate=1.2,
            heat_feedback=self._on_heat_feedback,
            power_capacity=12.0,
            power_per_shot=1.5,
            power_recharge_rate=0.8,
            power_feedback=self._on_power_feedback,
            obstruction_feedback=self._on_obstruction_feedback,
            orientation_blend=self._blend_with_rig,
            cooperative_threat_weight=1.6,
            cooperative_latency_decay=0.65,
            cooperative_confidence_exponent=1.15,
            telemetry_callback=self._on_telemetry,
            effects_callback=self._on_cinematic_effects,
            rl_training_callback=self._on_rl_training,
            telemetry_exporter=exporter,
            telemetry_capture_callback=self._on_capture_frame,
            rl_reward_target=0.6,
            rl_reward_adjust_rate=0.12,
            rl_reward_smoothing=0.25,
            rl_cooldown_bounds=(0.45, 1.6),
            rl_threat_bias_bounds=(0.6, 2.6),
        )
        self.turret = Turret(position=Vector3(0.0, 0.0, 0.0), config=config)
        self.telemetry_exporter = exporter
        self.cover_objects: List[Tuple[Vector3, float]] = [
            (Vector3(5.0, 0.0, 18.0), 3.5),
            (Vector3(-8.0, 0.0, 25.0), 4.0),
            (Vector3(2.0, 0.0, 32.0), 2.5),
        ]
        self.turret.config.obstruction_check = self._has_line_of_sight
        self.targets: List[SimulationTarget] = []
        self.time = 0.0
        self.next_ammo_cycle = 8.0
        self.manual_override_active = False
        self.manual_override_start = 16.0
        self.manual_override_end = 19.0
        self.feedback_events: List[str] = []
        self.obstruction_events: List[str] = []
        self.telemetry_log: List[TurretTelemetry] = []
        self.telemetry_overlay: str = ""
        self.sensor_ping_interval = 1.5
        self.next_sensor_ping = 2.0
        self.drone_ping_interval = 3.0
        self.next_drone_sweep = 1.2
        self.player_ping_interval = 4.5
        self.next_player_ping = 5.0
        self.effects_events: List[str] = []
        self.rl_events: List[str] = []
        self.rpc_events: List[str] = []
        self.designation_events: List[str] = []
        self.capture_events: List[str] = []
        self.capture_stream_events: List[str] = []
        self.pending_reward: Optional[float] = None

    def spawn_target(self, identifier: str) -> None:
        position = Vector3(
            random.uniform(-30.0, 30.0),
            random.uniform(-2.0, 10.0),
            random.uniform(20.0, 40.0),
        )
        velocity = Vector3(
            random.uniform(-5.0, 5.0),
            random.uniform(-1.0, 1.0),
            random.uniform(-5.0, -1.0),
        )
        acceleration = Vector3(
            random.uniform(-0.5, 0.5),
            random.uniform(-0.2, 0.0),
            random.uniform(-0.5, 0.0),
        )
        priority = random.randint(0, 2)
        self.targets.append(
            SimulationTarget(
                Target(identifier, position, velocity, velocity.y > 0, priority),
                acceleration,
            )
        )

    def step(self, dt: float) -> None:
        self.time += dt
        while self.time >= self.next_sensor_ping:
            self._broadcast_designations(("radar",))
            self.next_sensor_ping += self.sensor_ping_interval
        while self.time >= self.next_drone_sweep:
            self._broadcast_designations(("drone",))
            self.next_drone_sweep += self.drone_ping_interval
        while self.time >= self.next_player_ping:
            self._broadcast_designations(("player",))
            self.next_player_ping += self.player_ping_interval
        # Update target movement
        new_targets: List[SimulationTarget] = []
        for sim_target in self.targets:
            velocity = sim_target.target.velocity + sim_target.acceleration * dt
            position = sim_target.target.position + velocity * dt
            if position.distance_to(self.turret.position) < 100.0:
                new_targets.append(
                    SimulationTarget(
                        Target(
                            sim_target.target.id,
                            position,
                            velocity,
                            velocity.y > 0,
                            sim_target.target.priority,
                        ),
                        sim_target.acceleration,
                    )
                )
        self.targets = new_targets

        messages: List[str] = []
        if self.time >= self.next_ammo_cycle:
            ammo = self.turret.cycle_ammunition()
            messages.append(f"switched ammo -> {ammo.name}")
            self.next_ammo_cycle += 8.0

        if not self.manual_override_active and self.time >= self.manual_override_start:
            self.turret.engage_manual_override(
                120.0,
                5.0,
                waypoints=[
                    ManualWaypoint(120.0, 5.0, dwell_time=0.4, fire_burst=3, burst_interval=0.08),
                    ManualWaypoint(-70.0, 3.0, dwell_time=0.5),
                    ManualWaypoint(15.0, 0.0, dwell_time=0.6),
                ],
            )
            self.manual_override_active = True
            messages.append("manual override engaged")
        elif self.manual_override_active and self.time >= self.manual_override_end:
            self.turret.clear_manual_override()
            self.manual_override_active = False
            messages.append("manual override released")

        fired_at = self.turret.update(dt, (t.target for t in self.targets))
        yaw = self.turret.state.yaw_deg
        pitch = self.turret.state.pitch_deg
        ammo = self.turret.current_ammunition
        status = (
            f"time={self.time:4.1f}s yaw={yaw:6.1f} pitch={pitch:5.1f}"
            f" ammo={ammo.name:8s} heat={self.turret.state.heat:4.1f}"
            f" power={self.turret.state.power:4.1f}/{self.turret.config.power_capacity:4.1f}"
        )
        if self.turret.state.tracked_target:
            prediction = self.turret.state.last_prediction_time
            status += f" tracking={self.turret.state.tracked_target.id}"
            if prediction > 0:
                status += f" tti={prediction:4.2f}s"
        if self.turret.state.overheated:
            status += " [OVERHEATED]"
        if self.turret.state.manual_override:
            status += " [MANUAL]"
        if fired_at:
            status += f" -> Fired at target {fired_at}!"
        if self.turret.state.last_obstruction and self.turret.state.last_obstruction.blocked:
            sample = self.turret.state.last_obstruction
            status += " | LOS blocked"
            if sample.hit_position:
                status += f" at {sample.hit_position}"
        designation_count = len(self.turret.state.cooperative_designations)
        if designation_count:
            status += f" | designations={designation_count}"
        if self.designation_events:
            status += " | sensors=" + ", ".join(self.designation_events)
            self.designation_events.clear()
        if messages:
            status += " | " + ", ".join(messages)
        if self.feedback_events:
            status += " | feedback=" + ", ".join(self.feedback_events)
            self.feedback_events.clear()
        if self.obstruction_events:
            status += " | audio=" + ", ".join(self.obstruction_events)
            self.obstruction_events.clear()
        if self.effects_events:
            status += " | fx=" + ", ".join(self.effects_events)
            self.effects_events.clear()
        if self.rl_events:
            status += " | rl=" + ", ".join(self.rl_events)
            self.rl_events.clear()
        if self.rpc_events:
            status += " | stream=" + ", ".join(self.rpc_events)
            self.rpc_events.clear()
        if self.capture_events:
            status += " | capture=" + ", ".join(self.capture_events)
            self.capture_events.clear()
        if self.capture_stream_events:
            status += " | replay=" + ", ".join(self.capture_stream_events)
            self.capture_stream_events.clear()
        if self.telemetry_overlay:
            status += f" | {self.telemetry_overlay}"
            self.telemetry_overlay = ""
        print(status)

    def _has_line_of_sight(self, origin: Vector3, target: Vector3) -> ObstructionSample:
        direction = target - origin
        length_sq = direction.squared_magnitude()
        if length_sq == 0:
            return ObstructionSample(blocked=False, navigation_cost=1.0)
        for center, radius in self.cover_objects:
            oc = origin - center
            a = length_sq
            b = 2.0 * oc.dot(direction)
            c = oc.squared_magnitude() - radius ** 2
            discriminant = b ** 2 - 4 * a * c
            if discriminant < 0:
                continue
            sqrt_disc = math.sqrt(discriminant)
            t1 = (-b - sqrt_disc) / (2 * a)
            t2 = (-b + sqrt_disc) / (2 * a)
            if 0.0 < t1 < 1.0:
                hit_point = origin + direction * t1
                return ObstructionSample(blocked=True, hit_position=hit_point, navigation_cost=radius)
            if 0.0 < t2 < 1.0:
                hit_point = origin + direction * t2
                return ObstructionSample(blocked=True, hit_position=hit_point, navigation_cost=radius)
        return ObstructionSample(blocked=False, navigation_cost=1.0)

    def _broadcast_designations(self, sources: Tuple[str, ...]) -> None:
        if not self.targets:
            return
        designations: List[TargetDesignation] = []
        sensor_counts: Dict[str, int] = {}
        for sim_target in self.targets:
            distance = self.turret.position.distance_to(sim_target.target.position)
            if distance > self.turret.config.detection_radius * 1.4:
                continue
            proximity = max(0.0, 1.0 - distance / max(1.0, self.turret.config.detection_radius))
            airborne_bonus = 0.35 if sim_target.target.is_airborne else 0.0
            base_threat = (sim_target.target.priority + 1) * 0.35 + proximity + airborne_bonus
            if base_threat <= 0:
                continue
            for source in sources:
                if source == "radar":
                    threat = base_threat
                    ttl = 3.5
                    decay = threat * 0.35
                elif source == "drone":
                    threat = base_threat * 1.15 + 0.25
                    ttl = 1.6
                    decay = threat * 0.9 + 0.3
                    confidence = random.uniform(0.65, 0.85)
                    latency = random.uniform(0.05, 0.15)
                elif source == "player":
                    threat = base_threat * 0.8 + 0.6
                    ttl = 2.4
                    decay = threat * 0.5
                    confidence = random.uniform(0.5, 0.95)
                    latency = random.uniform(0.2, 0.6)
                    if random.random() < 0.3:
                        threat += 0.5
                else:
                    threat = base_threat
                    ttl = 2.0
                    decay = threat / ttl
                    confidence = random.uniform(0.55, 0.9)
                    latency = random.uniform(0.1, 0.25)
                if source == "radar":
                    confidence = random.uniform(0.85, 0.97)
                    latency = random.uniform(0.05, 0.12)
                sensor_id = f"{source}-{sim_target.target.id}"
                designations.append(
                    TargetDesignation(
                        target_id=sim_target.target.id,
                        threat=threat,
                        ttl=ttl,
                        sensor_id=sensor_id,
                        sensor_kind=source,
                        decay_rate=decay,
                        confidence=confidence,
                        latency=latency,
                    )
                )
                sensor_counts[source] = sensor_counts.get(source, 0) + 1
        if designations:
            self.turret.ingest_designations(designations)
            summary = ", ".join(f"{key}:{value}" for key, value in sensor_counts.items())
            self.designation_events.append(summary)

    def _on_heat_feedback(self, heat: float, capacity: float, overheated: bool) -> None:
        state = "overheated" if overheated else "cooling" if heat < capacity * 0.25 else "warm"
        self.feedback_events.append(f"heat {heat:3.1f} ({state})")

    def _on_power_feedback(self, power: float, capacity: float) -> None:
        if capacity <= 0:
            return
        ratio = power / capacity
        level = "low" if ratio < 0.25 else "charging" if ratio < 0.9 else "full"
        self.feedback_events.append(f"power {power:3.1f} ({level})")

    def _on_obstruction_feedback(self, sample: ObstructionSample) -> None:
        if sample.blocked:
            descriptor = "occluded"
            if sample.hit_position:
                descriptor += f" @{sample.hit_position.z:4.1f}m"
        else:
            descriptor = f"clear (cost={sample.navigation_cost:3.1f})"
        self.obstruction_events.append(descriptor)

    def _blend_with_rig(self, yaw: float, pitch: float) -> tuple[float, float]:
        sway = math.sin(self.turret.state.total_time * 0.6) * 2.0
        lift = math.sin(self.turret.state.total_time * 0.85) * 1.0
        return yaw + sway * 0.25, pitch + lift * 0.15

    def _on_telemetry(self, telemetry: TurretTelemetry) -> None:
        self.telemetry_log.append(telemetry)
        if len(self.telemetry_log) > 40:
            self.telemetry_log.pop(0)
        overlay = f"telemetry heat={telemetry.heat:3.1f} power={telemetry.power:3.1f}"
        if telemetry.cooperative_designation_count:
            overlay += f" coop={telemetry.cooperative_designation_count}"
        if telemetry.cooperative_threat_score > 0:
            overlay += f" threat={telemetry.cooperative_threat_score:3.2f}"
            if telemetry.cooperative_sensor_breakdown:
                details = ",".join(
                    f"{name}:{value:2.1f}"
                    for name, value in telemetry.cooperative_sensor_breakdown.items()
                )
                overlay += f" [{details}]"
            overlay += (
                f" conf={telemetry.cooperative_average_confidence:3.2f}"
                f" lat={telemetry.cooperative_average_latency:3.2f}"
            )
        if telemetry.fired_target:
            overlay += f" fired={telemetry.fired_target}"
        if telemetry.obstruction and telemetry.obstruction.blocked:
            overlay += " occluded"
        self.telemetry_overlay = overlay

    def _on_cinematic_effects(self, telemetry: TurretTelemetry) -> None:
        if telemetry.fired_target:
            effect = f"recoil->{telemetry.fired_target}"
            if telemetry.obstruction and telemetry.obstruction.blocked:
                effect += " debris"
            else:
                effect += " muzzle"
            self.effects_events.append(effect)
        elif telemetry.obstruction and telemetry.obstruction.blocked:
            self.effects_events.append("impact-dust")

    def _on_rl_training(self, telemetry: TurretTelemetry, features: Dict[str, float]) -> float:
        reward = features.get("cooperative_threat", 0.0) - features.get("heat_ratio", 0.0) * 2.0
        reward -= features.get("power_ratio", 0.0) * 0.5
        if telemetry.fired_target:
            reward += 1.0
        summary = f"reward={reward:+.2f}"
        self.rl_events.append(summary)
        self.pending_reward = reward
        return reward

    def _dispatch_rpc(self, method: str, payload: Dict[str, object]) -> None:
        tracked = payload.get("tracked_target") or "idle"
        heat = float(payload.get("heat", 0.0))
        threat = float(payload.get("cooperative_threat_score", 0.0))
        self.rpc_events.append(
            f"{method.split('.')[-1]}:{tracked} h={heat:3.1f} threat={threat:2.1f}"
        )

    def _on_capture_frame(self, telemetry: TurretTelemetry, frame: int) -> None:
        descriptor = f"frame{frame} yaw={telemetry.yaw_deg:5.1f}"
        if telemetry.tracked_target:
            descriptor += f" target={telemetry.tracked_target}"
        descriptor += f" scale={self.turret.state.rl_cooldown_scale:3.2f}"
        descriptor += f" bias={self.turret.state.rl_threat_bias:3.2f}"
        self.capture_events.append(descriptor)
        if self.pending_reward is not None:
            self.rl_events.append(
                f"adapt cd={self.turret.state.rl_cooldown_scale:3.2f}"
                f" bias={self.turret.state.rl_threat_bias:3.2f}"
            )
            self.pending_reward = None

    def _record_capture_stream(self, frame: int, payload: Dict[str, object]) -> None:
        tracked = payload.get("tracked_target") or "idle"
        self.capture_stream_events.append(f"f{frame}:{tracked}")


def main() -> None:
    simulation = TurretSimulation()
    for index in range(5):
        simulation.spawn_target(f"target-{index}")

    for _ in range(60):
        simulation.step(0.1)


if __name__ == "__main__":
    main()

