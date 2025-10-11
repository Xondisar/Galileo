"""Regression tests for the turret AI module."""
from __future__ import annotations

import math

from turret_ai.geometry import Vector3, solve_intercept_time
from turret_ai.turret import AmmunitionType, Target, Turret, TurretConfig


def test_target_selection_prefers_priority() -> None:
    turret = Turret(position=Vector3(0, 0, 0))
    low = Target("low", Vector3(5, 0, 10), Vector3(0, 0, 0), priority=0)
    high = Target("high", Vector3(4, 0, 8), Vector3(0, 0, 0), priority=2)

    selected = turret.select_target([low, high])

    assert selected is high


def test_turret_fires_when_aligned() -> None:
    config = TurretConfig(
        fire_arc_deg=10.0,
        max_turn_rate_deg=360.0,
        projectile_speed=50.0,
        fire_cooldown=0.05,
    )
    turret = Turret(position=Vector3(0, 0, 0), config=config)
    target = Target("enemy", Vector3(0, 0, 20), Vector3(0, 0, 0))

    turret.state.tracked_target = target
    fired = None
    for _ in range(10):
        fired = turret.update(0.1, [target])
        if fired:
            break

    assert fired == "enemy"


def test_turret_leads_moving_target() -> None:
    config = TurretConfig(
        fire_arc_deg=3.0,
        max_turn_rate_deg=720.0,
        fire_cooldown=0.05,
        max_prediction_time=5.0,
    )
    config.ammunition_types = (
        AmmunitionType("standard", projectile_speed=45.0, damage=10.0),
    )
    turret = Turret(position=Vector3(0, 0, 0), config=config)
    moving = Target("runner", Vector3(-10, 0, 40), Vector3(8, 0, -6))

    fired = None
    for _ in range(60):
        fired = turret.update(0.1, [moving])
        if fired:
            break
        moving = Target(
            moving.id,
            moving.predict_position(0.1),
            moving.velocity,
            moving.is_airborne,
            moving.priority,
        )

    assert fired == "runner"


def test_turret_forgets_target_after_memory() -> None:
    config = TurretConfig(target_memory=0.1)
    turret = Turret(position=Vector3(0, 0, 0), config=config)
    target = Target("ghost", Vector3(0, 0, 10), Vector3(0, 0, 0))

    turret.state.tracked_target = target
    turret.update(0.2, [])

    assert turret.state.tracked_target is None


def test_solve_intercept_time_handles_parallel_motion() -> None:
    origin = Vector3(0, 0, 0)
    target_position = Vector3(10, 0, 0)
    target_velocity = Vector3(0, 0, 5)
    projectile_speed = 10.0

    time = solve_intercept_time(origin, target_position, target_velocity, projectile_speed)

    assert math.isclose(time, math.sqrt(4 / 3), rel_tol=1e-3)


def test_obstruction_prevents_fire() -> None:
    config = TurretConfig(
        fire_arc_deg=2.0,
        max_turn_rate_deg=720.0,
        fire_cooldown=0.05,
        obstruction_check=lambda origin, target: False,
    )
    turret = Turret(position=Vector3(0, 0, 0), config=config)
    target = Target("blocked", Vector3(0, 0, 15), Vector3(0, 0, 0))

    turret.state.tracked_target = target
    for _ in range(10):
        assert turret.update(0.1, [target]) is None
