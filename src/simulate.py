"""Run a small command line simulation showcasing the turret AI."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from turret_ai.geometry import Vector3
from turret_ai.turret import (
    AmmunitionType,
    ManualWaypoint,
    ObstructionSample,
    Target,
    Turret,
    TurretConfig,
)


@dataclass
class SimulationTarget:
    target: Target
    acceleration: Vector3


class TurretSimulation:
    def __init__(self, seed: int = 42) -> None:
        random.seed(seed)
        ammo_types = (
            AmmunitionType("standard", projectile_speed=55.0, damage=10.0, heat_per_shot=1.2),
            AmmunitionType("piercing", projectile_speed=70.0, damage=14.0, heat_per_shot=1.8),
            AmmunitionType("rapid", projectile_speed=45.0, damage=6.0, heat_per_shot=0.8),
        )
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
        )
        self.turret = Turret(position=Vector3(0.0, 0.0, 0.0), config=config)
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
        if messages:
            status += " | " + ", ".join(messages)
        if self.feedback_events:
            status += " | feedback=" + ", ".join(self.feedback_events)
            self.feedback_events.clear()
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

    def _on_heat_feedback(self, heat: float, capacity: float, overheated: bool) -> None:
        state = "overheated" if overheated else "cooling" if heat < capacity * 0.25 else "warm"
        self.feedback_events.append(f"heat {heat:3.1f} ({state})")

    def _on_power_feedback(self, power: float, capacity: float) -> None:
        if capacity <= 0:
            return
        ratio = power / capacity
        level = "low" if ratio < 0.25 else "charging" if ratio < 0.9 else "full"
        self.feedback_events.append(f"power {power:3.1f} ({level})")


def main() -> None:
    simulation = TurretSimulation()
    for index in range(5):
        simulation.spawn_target(f"target-{index}")

    for _ in range(60):
        simulation.step(0.1)


if __name__ == "__main__":
    main()

