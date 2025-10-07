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
- `projectile_speed`: used alongside target velocity to compute intercept points.
- `max_prediction_time`: cap on lead prediction to avoid chasing very distant solutions.
- `fire_cooldown`: configurable cadence between shots.

## Feature ideas

The turret is intentionally modular so it can be extended. Some additions to
consider:

- Add obstruction checks (e.g. ray casting) so the turret respects cover.
- Support multiple ammunition types with different projectile speeds and damage.
- Introduce heat or power management systems that throttle firing cadence under sustained use.
- Layer additional behaviours such as idle scanning animations or manual override controls.

