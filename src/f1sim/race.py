from dataclasses import dataclass
from typing import List, Tuple



@dataclass(order=True)
class Event:
    t: float
    car_idx: str
    kind: str

class RaceSim:
    def __init__(
            self,
            track: Track,
            cars: List[]
    )