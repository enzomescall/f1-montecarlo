from dataclasses import dataclass, field
from typing import List, Tuple

Theta = Tuple[int, int]

@dataclass
class Constructor:
    """
    Basic information about a constructor
    """
    id: str
    points: float
    # Bayesian variables:
    pitstop_time: Theta # We can just add flat values for changing wings

@dataclass
class DriverCar:
    """
    Base data about a driver/constructor pairing which influences
    the performance of the car on the track 
    """
    id: str
    points: float
    # Car information:
    mech_reliability: Theta     # Priors for mech accident rate
    drag: Theta                 # Priors for straight line speed, affects dirty air behind
    drs_drag: Theta             # Priors for DRS straight line speed
    mech_grip: Theta            # Priors for cornering ability metric (CAM)
    downforce: Theta            # Priors for CAM, affected by dirty air

    # Joint Driver-Car information:
    race_pace: Theta            # Priors for raw race pace
    quali_pace: Theta           # Priors for raw quali pace
    accident_rate: Theta        # Priors for driver error rate
    tire_deg: Theta             # Priors for tire degradation rate
    fuel_usage: Theta           # Priors for fuel usage rate
    defensibility: Theta        # Priors for defensibility metric
    overtakeability: Theta      # Priors for overtakeability metric

    # Constructor information:
    cooperation: float          # Metric of how cooperative a driver is
    constructor: Constructor

@dataclass
class TireSpec:
    name: str
    deg_rate: float
    deg_curve: float = 0.0

@dataclass
class Tire:
    """
    One of the four tires in the car
    Calculate degredation at every tick
    """
    spec: TireSpec
    deg: float = 0.0    # value between 0 - 1, where 1 are completely degraded tires

    def d(self, l):
        # Formula for degradation, l is the load on the tires 
        self.deg += l * self.spec.deg_rate
    


@dataclass
class CarState:
    """
    Everything we track about the car over a lap
    """
    driver_car: DriverCar
    
    # Four tires
    tire_fr: Tire
    tire_fl: Tire
    tire_br: Tire
    tire_bl: Tire
    
    # General car status
    fuel: float = 1.0                   # abstraction of fuel load
    mechanical_health: float = 1.0      # abstraction of car component damage
    lap: int = 0                        # lap number
    ms: int = 0                         # minisector number in lap
    time_s: float = 0.0                 # time spent in minisector
    drs_open: bool = False
    retired: bool = False
    in_pit: bool = False
    track_pos_key: float = 0.0          # lap num + minisector num + time_s