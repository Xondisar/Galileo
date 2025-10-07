# Galileo Turret AI

This repository implements a lightweight STS 3D-inspired turret AI. It provides:

- Core turret logic with target selection, predictive intercept aiming, and firing heuristics.
- A simple command line simulation to visualise behaviour and real-time predictions.
- Automated tests covering key interactions.

## Getting started

The project uses Python 3.11+.

1. Create a virtual environment and install dependencies (only `pytest` for tests).

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```

2. Run the demo simulation:

   ```bash
   python -m src.simulate
   ```

3. Execute the test suite:

   ```bash
   pytest
   ```

## Project structure

- `src/turret_ai/geometry.py` – minimal 3D vector helpers.
- `src/turret_ai/turret.py` – turret controller and AI logic, including lead prediction and configurable cooldowns.
- `src/simulate.py` – command line simulation demonstrating the turret.
- `tests/` – unit tests.

## Configuration highlights

Key tuning parameters on `TurretConfig`:

- `max_turn_rate_deg`: constrain how quickly yaw and pitch respond.
- `fire_arc_deg`: allowable misalignment before firing.
- `ammunition_types`: define projectile speed, damage, and heat footprint for each ammo class. The active ammunition can be cycled at runtime.
- `obstruction_check`: optional callback used for ray/shape tests so the turret respects cover when lining up a shot.
- `heat_*` values: configure heat capacity, overheating thresholds, and passive dissipation to throttle sustained fire.
- `heat_feedback`: hook for relaying heat changes to VFX/audio or downstream systems.
- `power_*` values: optional energy management that throttles firing when batteries are drained.
- `max_prediction_time`: cap on lead prediction to avoid chasing very distant solutions.
- `fire_cooldown`: configurable cadence between shots.
- `idle_scan_*`: tune the amplitude and speed of the idle scanning animation when no targets are available.

## Advanced behaviours

Beyond predictive aiming, the turret now models:

- Multiple ammunition archetypes with distinct projectile speeds, damage, and heat costs, plus helpers to cycle or select ammunition in response to threats.
- Line-of-sight gating through a user-provided obstruction check that can return detailed scene query data (e.g. navmesh hits) so terrain and cover block shots while exposing impact metadata.
- Heat management that drives optional visual/audio feedback hooks and ties into configurable power draw requirements when firing.
- Idle scanning behaviour to keep the turret lively when no targets are tracked.
- Manual override controls with waypoint queues and scripted burst fire so designers can choreograph sequences or let players temporarily take command.

Manual override sequences are described with `ManualWaypoint` objects which include dwell windows and optional burst fire counts to choreograph camera-ready sweeps.

### Extensibility ideas

Future enhancements could include:

- Integrating cooperative target designations from allied sensors.
- Adding spatial audio occlusion based on the obstruction metadata.
- Driving animation rigs directly from the turret orientation to blend with character poses.

