# Galileo Turret AI

An STS 3D-inspired, AI-powered pan/tilt rifle turret controller featuring predictive aiming, cover awareness, ammunition loadouts, heat management, and optional designer overrides.

## Features

- Target acquisition, prioritisation, and predictive lead calculation using analytical intercept solving for pan-and-tilt turrets.
- Configurable firing logic with cooldowns, fire arcs, and obstruction checks that can run full scene queries or navmesh raycasts.
- Multiple ammunition types with per-shot projectile speed, damage, heat, and power draw attributes plus helpers to select or cycle loadouts at runtime.
- Heat and power budget systems that throttle cadence, trigger feedback callbacks, and respect cooling dynamics under sustained fire.
- Cooperative target designations that fuse radar, drone, and player pings with per-sensor decay, confidence, and latency weighting for contested airspace.
- Idle scanning, manual override waypoint queues, and scripted burst-fire behaviours for cinematic or player-directed control.
- Obstruction metadata hooks that can drive spatial audio occlusion, cinematic recoil, muzzle flash, or navmesh costs.
- Orientation blending so turret aim can be layered with character rigs or IK solvers.
- Adaptive reinforcement-learning reward integration that feeds rewards back into cooldown and threat weighting for player-tailored difficulty.
- Telemetry streaming suitable for dashboards, profilers, reinforcement-learning agents, and WebSocket/RPC exports alongside capture overlays for replays or broadcast graphics.
An STS 3D-inspired turret controller featuring predictive aiming, cover awareness, ammunition loadouts, heat management, and optional designer overrides.

## Features

- Target acquisition, prioritisation, and predictive lead calculation using analytical intercept solving.
- Configurable firing logic with cooldowns, fire arcs, and obstruction checks that can run full scene queries or navmesh raycasts.
- Multiple ammunition types with per-shot projectile speed, damage, heat, and power draw attributes plus helpers to select or cycle loadouts at runtime.
- Heat and power budget systems that throttle cadence, trigger feedback callbacks, and respect cooling dynamics under sustained fire.
- Cooperative target designations and threat weighting sourced from allied sensors for coordinated defence networks.
- Idle scanning, manual override waypoint queues, and scripted burst-fire behaviours for cinematic or player-directed control.
- Obstruction metadata hooks that can drive spatial audio occlusion, impact effects, or navmesh costs.
- Orientation blending so turret aim can be layered with character rigs or IK solvers.
- Telemetry streaming suitable for dashboards, profilers, or remote debugging tools.
- Idle scanning, manual override waypoint queues, and scripted burst-fire behaviours for cinematic or player-directed control.
- Lightweight vector math utilities, simulation CLI, and comprehensive unit tests.

## Getting started

The project targets **Python 3.11+**.

1. Create and activate a virtual environment, then install development dependencies:
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

2. Run the interactive simulation demo:
2. Run the demo simulation:

   ```bash
   python -m src.simulate
   ```

3. Execute the automated tests:
3. Execute the test suite:

   ```bash
   pytest
   ```

## Project layout

| Path | Description |
| --- | --- |
| `src/turret_ai/geometry.py` | Minimal vector helpers for yaw/pitch transforms and intercept calculations. |
| `src/turret_ai/turret.py` | Turret controller implementation with ammunition, heat, power, obstruction, and override systems. |
| `src/simulate.py` | CLI simulation that visualises tracking, allied designations, rig blending, spatial occlusion, ammunition cycling, and feedback hooks. |
| `tests/` | Pytest suite covering predictive aiming, manual overrides, obstruction checks, heat throttling, telemetry, and ammunition flow. |
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
- `obstruction_feedback`: companion callback for piping line-of-sight metadata into spatial audio or VFX systems.
- `heat_*` values: configure heat capacity, cooling thresholds, and dissipation rates.
- `heat_feedback`: callback fired when heat changes so you can drive VFX, audio, or UI.
- `power_*` values: tune the energy system so low reserves pause firing until recharged.
- `idle_scan_*`: controls idle scanning amplitude and cadence when no targets are present.
- `manual_override`: supply scripted waypoint queues and burst-fire settings for choreographed sequences.
- `cooperative_threat_weight` & `ingest_designations(...)`: blend allied sensor designations with intrinsic priority scores.
- `cooperative_latency_decay` / `cooperative_confidence_exponent`: control how latency and confidence weighting influence allied designations.
- `orientation_blend`: blend final yaw/pitch with rig or IK solvers before rendering.
- `telemetry_callback`: stream per-tick `TurretTelemetry` snapshots to dashboards or profilers.
- `effects_callback`: emit combined telemetry and obstruction data to trigger recoil, muzzle flash, or debris effects.
- `rl_training_callback`: capture feature vectors for reinforcement-learning agents optimising turret heuristics, returning reward values to drive adaptive tuning.
- `telemetry_capture_callback`: receive frame-indexed telemetry alongside gameplay capture feeds.
- `rl_reward_*`: configure reward smoothing, targets, and clamps for adaptive tuning.
- `telemetry_exporter`: forward telemetry via WebSockets, capture overlays, or custom RPC dispatchers using the bundled exporters (the WebSocket variant requires the `websockets` package).

## Extensibility ideas

- Introduce predictive countermeasure deployment (e.g., smoke, ECM) when telemetry reports contested line-of-sight.
- Add network replication layers that forward cooperative designations between multiple turrets.
- Feed capture-aligned telemetry into automated replay editors for esport or broadcast tooling.
- `orientation_blend`: blend final yaw/pitch with rig or IK solvers before rendering.
- `telemetry_callback`: stream per-tick `TurretTelemetry` snapshots to dashboards or profilers.

## Extensibility ideas

- Fuse networked radar, drone, or player pings into richer cooperative designation logic with decay per sensor.
- Drive cinematic recoil, muzzle flash, or debris effects by combining telemetry snapshots with obstruction metadata.
- Train reinforcement-learning agents on the telemetry stream to optimise ammunition usage or prioritisation heuristics.
- Export telemetry over WebSockets or game-specific RPC to integrate with external analytics suites.

## Extensibility ideas

- Integrate cooperative target designations or threat scoring from allied sensors.
- Feed obstruction metadata into spatial audio occlusion or impact effects.
- Blend turret orientation with animation rigs or IK solvers for character-driven platforms.
- Surface telemetry to external monitoring or debugging dashboards.

## License

This project is provided for demonstration purposes; adapt or extend it to match your game's licensing needs.
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

