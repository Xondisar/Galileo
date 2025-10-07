# Galileo Turret AI

An STS 3D-inspired turret controller featuring predictive aiming, cover awareness, ammunition loadouts, heat management, and optional designer overrides.

## Features

- Target acquisition, prioritisation, and predictive lead calculation using analytical intercept solving.
- Configurable firing logic with cooldowns, fire arcs, and obstruction checks that can run full scene queries or navmesh raycasts.
- Multiple ammunition types with per-shot projectile speed, damage, heat, and power draw attributes plus helpers to select or cycle loadouts at runtime.
- Heat and power budget systems that throttle cadence, trigger feedback callbacks, and respect cooling dynamics under sustained fire.
- Idle scanning, manual override waypoint queues, and scripted burst-fire behaviours for cinematic or player-directed control.
- Lightweight vector math utilities, simulation CLI, and comprehensive unit tests.

## Getting started

The project targets **Python 3.11+**.

1. Create and activate a virtual environment, then install development dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```

2. Run the interactive simulation demo:

   ```bash
   python -m src.simulate
   ```

3. Execute the automated tests:

   ```bash
   pytest
   ```

## Project layout

| Path | Description |
| --- | --- |
| `src/turret_ai/geometry.py` | Minimal vector helpers for yaw/pitch transforms and intercept calculations. |
| `src/turret_ai/turret.py` | Turret controller implementation with ammunition, heat, power, obstruction, and override systems. |
| `src/simulate.py` | CLI simulation that visualises tracking, obstruction sampling, ammunition cycling, and heat feedback hooks. |
| `tests/` | Pytest suite covering predictive aiming, manual overrides, obstruction checks, heat throttling, and ammunition flow. |

## Configuration highlights

Important knobs on `TurretConfig`:

- `max_turn_rate_deg`: constrains yaw/pitch speed when tracking targets.
- `fire_arc_deg`: tolerance before a shot may be fired.
- `max_prediction_time`: prevents leading calculations from chasing extremely distant solutions.
- `fire_cooldown`: sets the minimum time between shots.
- `ammunition_types`: registers available ammunition archetypes with projectile speed, damage, heat, and power draw metadata.
- `obstruction_check`: optional callback returning obstruction metadata; use it to hook navmesh or physics queries.
- `heat_*` values: configure heat capacity, cooling thresholds, and dissipation rates.
- `heat_feedback`: callback fired when heat changes so you can drive VFX, audio, or UI.
- `power_*` values: tune the energy system so low reserves pause firing until recharged.
- `idle_scan_*`: controls idle scanning amplitude and cadence when no targets are present.
- `manual_override`: supply scripted waypoint queues and burst-fire settings for choreographed sequences.

## Extensibility ideas

- Integrate cooperative target designations or threat scoring from allied sensors.
- Feed obstruction metadata into spatial audio occlusion or impact effects.
- Blend turret orientation with animation rigs or IK solvers for character-driven platforms.
- Surface telemetry to external monitoring or debugging dashboards.

## License

This project is provided for demonstration purposes; adapt or extend it to match your game's licensing needs.
