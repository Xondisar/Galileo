"""Run a small command line simulation showcasing the turret AI."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List

from turret_ai.geometry import Vector3
from turret_ai.turret import Target, Turret


@dataclass
class SimulationTarget:
    target: Target
    acceleration: Vector3


class TurretSimulation:
    def __init__(self, seed: int = 42) -> None:
        random.seed(seed)
        self.turret = Turret(position=Vector3(0.0, 0.0, 0.0))
        self.targets: List[SimulationTarget] = []
        self.time = 0.0

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

        fired_at = self.turret.update(dt, (t.target for t in self.targets))
        yaw = self.turret.state.yaw_deg
        pitch = self.turret.state.pitch_deg
        status = f"time={self.time:4.1f}s yaw={yaw:6.1f} pitch={pitch:5.1f}"
        if self.turret.state.tracked_target:
            prediction = self.turret.state.last_prediction_time
            status += f" tracking={self.turret.state.tracked_target.id}"
            if prediction > 0:
                status += f" tti={prediction:4.2f}s"
        if fired_at:
            status += f" -> Fired at target {fired_at}!"
        print(status)


def main() -> None:
    simulation = TurretSimulation()
    for index in range(5):
        simulation.spawn_target(f"target-{index}")

    for _ in range(60):
        simulation.step(0.1)


if __name__ == "__main__":
    main()

