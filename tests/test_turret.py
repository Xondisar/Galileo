import math

from turret_ai.geometry import Vector3, solve_intercept_time
from turret_ai.turret import AmmunitionType, Target, Turret, TurretConfig


def test_target_selection_prefers_priority():
    turret = Turret(position=Vector3(0, 0, 0))
    low = Target("low", Vector3(5, 0, 10), Vector3(0, 0, 0), priority=0)
    high = Target("high", Vector3(4, 0, 8), Vector3(0, 0, 0), priority=2)

    selected = turret.select_target([low, high])

    assert selected is high


def test_turret_fires_when_aligned():
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


def test_turret_leads_moving_target():
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


def test_turret_forgets_target_after_memory():
    config = TurretConfig(target_memory=0.1)
    turret = Turret(position=Vector3(0, 0, 0), config=config)
    target = Target("ghost", Vector3(0, 0, 10), Vector3(0, 0, 0))

    turret.state.tracked_target = target
    turret.update(0.2, [])

    assert turret.state.tracked_target is None


def test_solve_intercept_time_handles_parallel_motion():
    origin = Vector3(0, 0, 0)
    target_position = Vector3(10, 0, 0)
    target_velocity = Vector3(0, 0, 5)
    projectile_speed = 10.0

    time = solve_intercept_time(origin, target_position, target_velocity, projectile_speed)

    assert math.isclose(time, math.sqrt(4 / 3), rel_tol=1e-3)


def test_obstruction_prevents_fire():
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

    assert turret.state.cooldown == 0.0


def test_heat_management_throttles_firing():
    ammo = AmmunitionType("burst", projectile_speed=60.0, damage=15.0, heat_per_shot=5.0)
    config = TurretConfig(
        fire_arc_deg=5.0,
        max_turn_rate_deg=720.0,
        fire_cooldown=0.05,
        overheat_threshold=5.0,
        heat_resume_threshold=1.0,
        heat_capacity=6.0,
        heat_dissipation_rate=0.5,
        ammunition_types=(ammo,),
    )
    turret = Turret(position=Vector3(0, 0, 0), config=config)
    target = Target("runner", Vector3(0, 0, 20), Vector3(0, 0, 0))

    turret.state.tracked_target = target
    first_shot = None
    for _ in range(5):
        fired = turret.update(0.1, [target])
        if fired:
            first_shot = fired
            break

    assert first_shot == "runner"
    assert turret.state.overheated

    cooled = False
    fired_again = None
    for _ in range(200):
        fired = turret.update(0.1, [target])
        if not turret.state.overheated:
            cooled = True
        if cooled and fired:
            fired_again = fired
            break

    assert cooled
    assert fired_again == "runner"


def test_ammunition_switch_updates_prediction():
    slow = AmmunitionType("slow", projectile_speed=30.0, damage=8.0)
    fast = AmmunitionType("fast", projectile_speed=80.0, damage=6.0)
    config = TurretConfig(
        fire_arc_deg=3.0,
        max_turn_rate_deg=720.0,
        fire_cooldown=0.05,
        max_prediction_time=5.0,
        ammunition_types=(slow, fast),
        default_ammunition="slow",
    )
    turret = Turret(position=Vector3(0, 0, 0), config=config)
    moving = Target("runner", Vector3(-10, 0, 40), Vector3(8, 0, -6))

    for _ in range(10):
        turret.update(0.1, [moving])
        moving = Target(
            moving.id,
            moving.predict_position(0.1),
            moving.velocity,
            moving.is_airborne,
            moving.priority,
        )

    slow_time = turret.state.last_prediction_time

    turret.set_ammunition("fast")
    for _ in range(10):
        turret.update(0.1, [moving])
        moving = Target(
            moving.id,
            moving.predict_position(0.1),
            moving.velocity,
            moving.is_airborne,
            moving.priority,
        )

    fast_time = turret.state.last_prediction_time

    assert fast_time < slow_time


def test_idle_scan_animates_without_targets():
    turret = Turret(position=Vector3(0, 0, 0))
    initial_yaw = turret.state.yaw_deg

    for _ in range(20):
        turret.update(0.1, [])

    assert not math.isclose(turret.state.yaw_deg, initial_yaw)


def test_manual_override_sets_orientation():
    turret = Turret(position=Vector3(0, 0, 0))
    turret.engage_manual_override(45.0, 10.0)

    for _ in range(10):
        turret.update(0.1, [])

    assert math.isclose(turret.state.yaw_deg, 45.0, abs_tol=1.0)
    assert math.isclose(turret.state.pitch_deg, 10.0, abs_tol=1.0)

