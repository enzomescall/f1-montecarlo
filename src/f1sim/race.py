from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from agents import DriverCar, TireSpec
from track import Track



@dataclass(order=True)
class Event:
    t: float
    car_idx: str
    kind: str

class RaceSim:
     def __init__(
        self,
        track: Track,
        grid: List[DriverCar],
        race_laps: int,
        strat_plan: Dict[str, List[Tuple[int,str]]],  # {code: [(pit_on_lap, compound), ...]}
        seed: Optional[int] = None,
    ):    
        return None