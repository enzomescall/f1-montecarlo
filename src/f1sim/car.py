from dataclasses import dataclass, field
from typing

@dataclass
class Driver:
    """
    Base data about a driver/constructor pairing which influences
    the performance of the car on the track 
    """
    id: str
    pace_theta: List[float, float]

@dataclass
class CarState:
    