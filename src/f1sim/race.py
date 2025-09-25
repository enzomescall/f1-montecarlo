from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional 
from agents import DriverCar, TireSpec, CarState
from track import Track
import math, random, heapq



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
        p_accident_per_ms: float = 1e-5,
        sc_prob_if_accident: float = 0.35,
        vsc_prob_if_accident: float = 0.35,
        dirty_air_pen_s: float = 0.010,   # per aero minisector when <0.8s behind
        slipstream_bonus_s: float = 0.006,# per straight minisector when <1.0s behind
        drs_bonus_s: float = 0.012,       # per DRS minisector when DRS active
    ):
        self.rng = random.Random(seed)
        self.tr = track
        self.field = []  # fill these out
        self.race_laps = race_laps
        self.strat = strat_plan
        self.events: List[Event] = []
        self.flags = {"SC": False, "VSC": False}, 
        self.params = dict(
            p_accident=p_accident_per_ms, sc_p=sc_prob_if_accident, vsc_p=vsc_prob_if_accident,
            dirty=dirty_air_pen_s, slip=slipstream_bonus_s, drs=drs_bonus_s,
        )

    # --- public API ---
    def run(self) -> List[CarState]:
        # seed initial “advance” events
        for i, car in enumerate(self.field):
            heapq.heappush(self.events, Event(0.0, i, "advance"))
        while self.events:
            ev = heapq.heappop(self.events)
            car = self.field[ev.car_idx]
            if car.retired: continue
            if ev.kind == "advance":
                self._advance_ms(ev.car_idx, ev.t)
            elif ev.kind == "pit_done":
                self._exit_pit(ev.car_idx, ev.t)
            elif ev.kind == "sc_end":
                self._end_sc(ev.t)
            # optional: vsc_end, penalties, etc.
            if self._race_over(): break
        # final order by total time, then track_pos
        return sorted(self.field, key=lambda c: (c.lap < self.race_laps, c.t))

    # --- mechanics ---
    def _advance_ms(self, i: int, now: float):
        car = self.field[i]
        if car.in_pit or car.retired: return

        tr = self.tr
        # compute clean baseline minisector time
        base_lap = self._base_lap_time(car)
        t_ms = base_lap * tr.minisector_weights[car.ms]

        # add micro noise and lap shock fraction
        t_ms += self.rng.gauss(0, car.driver.minisector_noise)
        t_ms += self.rng.gauss(0, car.driver.lap_variance) / tr.N_ms

        # traffic effects: need order of cars at time "now"
        order = self._race_order()
        ahead = self._car_ahead(i, order)
        gap_s = self._gap_to_ahead(i, ahead)

        # DRS detection
        if car.ms in tr.drs_detection_ms:
            car.drs_enabled = (gap_s is not None and gap_s <= 1.0)

        # aero / straight adjustments
        if ahead is not None and gap_s is not None:
            if car.ms in tr.aero_ms and gap_s < 0.8:
                t_ms += self.params["dirty"]
            if car.ms in tr.straight_ms and gap_s < 1.0:
                t_ms -= self.params["slip"]
            if car.drs_enabled and self._in_drs_zone(car.ms):
                t_ms -= self.params["drs"]

        # Safety Car / VSC multipliers
        if self.flags["SC"]:
            t_ms *= 1.60  # big slow; field bunches (overtakes off)
        elif self.flags["VSC"]:
            t_ms *= 1.30

        # accident chance in this minisector
        if not self.flags["SC"] and not self.flags["VSC"]:
            if self.rng.random() < self.params["p_accident"]:
                car.retired = True
                # possibly deploy SC/VSC
                r = self.rng.random()
                if r < self.params["sc_p"]:
                    self._start_sc(now)
                elif r < self.params["sc_p"] + self.params["vsc_p"]:
                    self._start_vsc(now)
                return

        # schedule next advance
        car.t = max(car.t, now) + max(0.0, t_ms)
        # try overtake at suitable points (not under SC/VSC)
        if not (self.flags["SC"] or self.flags["VSC"]) and ahead is not None:
            self._maybe_overtake(i, ahead, gap_s)

        # move minisector
        car.ms += 1
        if car.ms >= tr.N_ms:
            car.ms = 0
            car.lap += 1
            # fuel burn & tire wear
            for c in self.field:
                if not c.retired:
                    c.fuel_kg = max(0.0, c.fuel_kg - self._fuel_burn_per_lap(c))
            car.wear_laps += 1.0
            # pit decision at lap boundary
            self._maybe_pit(i)

        # update track position for ordering
        car.track_pos = car.lap + car.ms / tr.N_ms

        heapq.heappush(self.events, Event(car.t, i, "advance"))

    def _base_lap_time(self, car: CarState) -> float:
        d = car.driver
        # fuel penalty (s/lap)
        fuel_pen = d.fuel_s_per_kg * car.fuel_kg
        # tire wear penalty (allow non-linear)
        wear_pen = car.compound.deg_s_per_lap * car.wear_laps * (1.0 + car.compound.deg_curve * car.wear_laps)
        return d.base_pace + fuel_pen + wear_pen

    def _in_drs_zone(self, ms: int) -> bool:
        return any(a <= ms < b for a, b in self.tr.drs_zones)

    def _race_order(self) -> List[int]:
        # indices sorted by track_pos (descending), tie-break by t
        idxs = [i for i,c in enumerate(self.field) if not c.retired]
        return sorted(idxs, key=lambda i: (-self.field[i].track_pos, self.field[i].t))

    def _car_ahead(self, i: int, order: List[int]) -> Optional[int]:
        if len(order) <= 1: return None
        pos = order.index(i)
        return order[pos-1] if pos > 0 else None

    def _gap_to_ahead(self, i: int, j: Optional[int]) -> Optional[float]:
        if j is None: return None
        return max(0.0, self.field[j].t - self.field[i].t)

    def _maybe_overtake(self, i: int, j: int, gap_s: float):
        if gap_s is None or gap_s > 1.5: return  # too far
        car = self.field[i]; ahead = self.field[j]
        # only attempt at straight or DRS zone
        if self.field[i].ms not in self.tr.straight_ms and not self._in_drs_zone(self.field[i].ms):
            return
        # effective delta pace: positive if attacker faster (s/lap -> s/ms approx)
        dpace = (self._base_lap_time(ahead) - self._base_lap_time(car)) / self.tr.N_ms
        x = (self.params["a"] * dpace
             + self.params["b"] * (1.0 if car.drs_enabled else 0.0)
             + self.params["c"] * (1.0 if self.field[i].ms in self.tr.straight_ms else 0.0)
             - self.params["d"] * self.tr.overtake_difficulty)
        p = 1.0 / (1.0 + math.exp(-x))
        if self.rng.random() < p:
            # pass: swap their times slightly (attacker ahead by small margin)
            eps = 0.05
            car.t = max(car.t, ahead.t) - eps
            self._swap_order(i, j)
        else:
            # fail: attacker loses a bit
            car.t += 0.08

    def _swap_order(self, i: int, j: int):
        # swap track_pos ordering minimally: nudge minisector fractions
        self.field[i].track_pos += 1e-6
        self.field[j].track_pos -= 1e-6

    def _fuel_burn_per_lap(self, car: CarState) -> float:
        # simple constant burn; calibrate per track
        return 1.4

    def _maybe_pit(self, i: int):
        car = self.field[i]
        plan = self.strat.get(car.driver.code, [])
        for (lap, compound) in plan:
            if lap == car.lap and not car.in_pit and not self.flags["SC"]:
                car.in_pit = True
                car.t += car.driver.pit_loss_s
                heapq.heappush(self.events, Event(car.t, i, "pit_done"))
                return

    def _exit_pit(self, i: int, now: float):
        car = self.field[i]
        # advance stint
        plan = self.strat[car.driver.code]
        # pop current plan element if matching this lap
        if plan and plan[0][0] == car.lap:
            _, comp = plan.pop(0)
            car.compound = self.tires[comp]
        car.wear_laps = 0.0
        car.in_pit = False
        # schedule next advance event at same minisector (pit lane modeled abstractly)
        heapq.heappush(self.events, Event(now, i, "advance"))

    def _start_sc(self, now: float):
        if self.flags["SC"]: return
        self.flags["SC"] = True
        # bunch field to reduce gaps progressively (simplified)
        # schedule SC end (random 3-6 laps equivalent in time); using time proxy here
        end_t = now + self.rng.uniform(180.0, 360.0)
        heapq.heappush(self.events, Event(end_t, -1, "sc_end"))

    def _start_vsc(self, now: float):
        if self.flags["VSC"]: return
        self.flags["VSC"] = True
        end_t = now + self.rng.uniform(60.0, 120.0)
        heapq.heappush(self.events, Event(end_t, -1, "sc_end"))

    def _end_sc(self, now: float):
its t
