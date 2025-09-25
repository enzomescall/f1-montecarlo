# src/f1sim/__init__.py
"""
f1sim: Monte Carlo Formula 1 race simulator.
"""

from .race import RaceSim
from .track import Track
from .agents import DriverCar, CarState, TireSpec

__all__ = ["RaceSim", "Track", "DriverCar", "CarState", "TireSpec"]
__version__ = "0.0.1    "