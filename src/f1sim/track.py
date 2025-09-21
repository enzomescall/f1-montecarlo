from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class Track:
    name: str
    minisector_weights: List[float]   # sum ≈ 1.0 over a lap
    drs_zones: List[Tuple[int,int]]   # [(ms_start, ms_end), ...]
    drs_detection_ms: List[int]       # minisector indices that detect <1.0s gap
    overtake_difficulty: float        # 0 easy .. 1.5 very hard
    straight_ms: set[int] = field(default_factory=set)  # helps slipstream/DRS
    aero_ms: set[int] = field(default_factory=set)      # dirty air penalties

    @property
    def N_ms(self) -> int: return len(self.minisector_weights)