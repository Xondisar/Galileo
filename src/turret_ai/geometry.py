"""Basic 3D vector math utilities for the turret simulation."""
from __future__ import annotations

from dataclasses import dataclass
import math

EPSILON = 1e-6


@dataclass(frozen=True)
class Vector3:
    """Simple immutable 3D vector with helper operations."""

    x: float
    y: float
    z: float

    def __add__(self, other: "Vector3") -> "Vector3":
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vector3") -> "Vector3":
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vector3":
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def magnitude(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)

    def squared_magnitude(self) -> float:
        return self.x ** 2 + self.y ** 2 + self.z ** 2

    def normalized(self) -> "Vector3":
        mag = self.magnitude()
        if mag == 0:
            raise ValueError("Cannot normalize zero-length vector")
        return Vector3(self.x / mag, self.y / mag, self.z / mag)

    def dot(self, other: "Vector3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def distance_to(self, other: "Vector3") -> float:
        return (self - other).magnitude()

    def horizontal_angle_to(self, other: "Vector3") -> float:
        """Angle in radians between projections on the XZ-plane."""
        v1 = Vector3(self.x, 0.0, self.z)
        v2 = Vector3(other.x, 0.0, other.z)
        denom = v1.magnitude() * v2.magnitude()
        if denom == 0:
            return 0.0
        cos_theta = max(-1.0, min(1.0, v1.dot(v2) / denom))
        return math.acos(cos_theta)

    def vertical_angle_to(self, other: "Vector3") -> float:
        """Angle in radians between projections on the Y-axis plane."""
        v1 = Vector3(0.0, self.y, self.magnitude())
        v2 = Vector3(0.0, other.y, other.magnitude())
        denom = v1.magnitude() * v2.magnitude()
        if denom == 0:
            return 0.0
        cos_theta = max(-1.0, min(1.0, v1.dot(v2) / denom))
        return math.acos(cos_theta)


UP = Vector3(0.0, 1.0, 0.0)


def solve_intercept_time(
    origin: Vector3,
    target_position: Vector3,
    target_velocity: Vector3,
    projectile_speed: float,
    max_time: float | None = None,
) -> float:
    """Return the positive intercept time for a projectile, or ``0`` when none.

    The computation solves ``|target_position + target_velocity * t - origin| =``
    ``projectile_speed * t`` for ``t`` and returns the smallest positive root. If
    the projectile speed is zero or no positive solution exists the function
    falls back to ``0``.
    """

    if projectile_speed <= 0:
        return 0.0

    to_target = target_position - origin
    target_speed_sq = target_velocity.squared_magnitude()
    projectile_speed_sq = projectile_speed ** 2

    a = target_speed_sq - projectile_speed_sq
    b = 2.0 * to_target.dot(target_velocity)
    c = to_target.squared_magnitude()

    if abs(a) < EPSILON:
        if abs(b) < EPSILON:
            return 0.0
        time = -c / b
        if time <= 0:
            return 0.0
        if max_time is not None:
            time = min(time, max_time)
        return time

    discriminant = b ** 2 - 4 * a * c
    if discriminant < 0:
        return 0.0

    sqrt_disc = math.sqrt(discriminant)
    t1 = (-b - sqrt_disc) / (2 * a)
    t2 = (-b + sqrt_disc) / (2 * a)
    candidates = [t for t in (t1, t2) if t > EPSILON]
    if not candidates:
        return 0.0

    time = min(candidates)
    if max_time is not None:
        time = min(time, max_time)
    return time

