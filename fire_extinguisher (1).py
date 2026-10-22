#!/usr/bin/env python3
"""
fire_extinguisher.py  -  Fire Extinguisher Simulator
BTech Fire Technology & Safety mini project (pure Python, no libraries needed)

What it does
------------
* Models the 6 fire classes (A, B, C, D, E, K) and 6 extinguisher agents.
* Checks agent-vs-fire compatibility (correct / ineffective / DANGEROUS).
* Simulates a real extinguisher: pressure gauge, agent quantity, throw range.
* Walks you through the PASS technique (Pull, Aim, Squeeze, Sweep).
* AUTO mode: a "smart" extinguisher detects the fire class and picks the agent.

Run it
------
    python fire_extinguisher.py                      # interactive, asks you
    python fire_extinguisher.py --fire B --agent co2 # choose directly
    python fire_extinguisher.py --fire E --auto      # smart auto mode
    python fire_extinguisher.py --fire K --agent water --fast   # see a wrong choice
"""

import argparse
import random
import time

# --------------------------------------------------------------------------
# 1. Fire science data
# --------------------------------------------------------------------------
FIRE_CLASSES = {
    "A": "Ordinary combustibles (wood, paper, cloth, plastic)",
    "B": "Flammable liquids (petrol, diesel, oil, paint)",
    "C": "Flammable gases (LPG, methane, propane)",
    "D": "Combustible metals (magnesium, sodium, aluminium powder)",
    "E": "Live electrical equipment (panels, wiring, appliances)",
    "K": "Cooking oils and fats (kitchen deep fryers)",
}

# agent -> (fire classes it is rated for, effective throw range in metres, kg of agent per second)
AGENTS = {
    "water":        ({"A"},                  8.0, 0.60),
    "foam":         ({"A", "B"},             4.0, 0.40),
    "co2":          ({"B", "E"},             2.0, 0.30),
    "dry_powder":   ({"A", "B", "C", "E"},   4.0, 0.35),   # ABC powder
    "wet_chemical": ({"K", "A"},             3.0, 0.30),
    "d_powder":     ({"D"},                  2.5, 0.30),   # special metal-fire powder
}

# Wrong choices that make things WORSE (not just useless)
DANGEROUS = {
    ("water", "B"): "Water spreads burning liquid and makes the fire bigger!",
    ("water", "D"): "Water reacts violently with burning metal (explosion risk)!",
    ("water", "E"): "Water conducts electricity - ELECTROCUTION risk!",
    ("water", "K"): "Water on hot oil flashes to steam and throws burning oil (flare-up)!",
    ("foam", "E"):  "Foam is water-based and conducts electricity - electrocution risk!",
    ("foam", "K"):  "Foam on hot oil causes a violent flare-up!",
    ("foam", "D"):  "Water-based foam reacts violently with burning metal!",
}

# What the "smart" extinguisher picks for each class
BEST_AGENT = {
    "A": "water", "B": "foam", "C": "dry_powder",
    "D": "d_powder", "E": "co2", "K": "wet_chemical",
}


# --------------------------------------------------------------------------
# 2. The fire
# --------------------------------------------------------------------------
class Fire:
    def __init__(self, fire_class, heat=80.0):
        self.fire_class = fire_class
        self.heat = heat  # 0 = out, 100 = fully developed

    @property
    def is_out(self):
        return self.heat <= 0

    def grow(self, amount=1.5):
        self.heat = min(100.0, self.heat + amount)

    def apply(self, amount):
        self.heat = min(100.0, max(0.0, self.heat - amount))


# --------------------------------------------------------------------------
# 3. The extinguisher
# --------------------------------------------------------------------------
class Extinguisher:
    FULL_PRESSURE_BAR = 14.0

    def __init__(self, agent, capacity_kg=4.0):
        if agent not in AGENTS:
            raise ValueError(f"Unknown agent '{agent}'. Choose from: {', '.join(AGENTS)}")
        self.agent = agent
        self.classes, self.range_m, self.rate_kg_s = AGENTS[agent]
        self.capacity = capacity_kg
        self.agent_left = capacity_kg
        self.pin_pulled = False
        self.aimed = False

    # -- gauge -----------------------------------------------------------
    @property
    def pressure(self):
        return self.FULL_PRESSURE_BAR * (self.agent_left / self.capacity)

    def gauge(self):
        p = self.pressure
        zone = "GREEN (ready)" if p >= 12 else "YELLOW (low)" if p >= 6 else "RED (low - recharge after use)"
        return f"{p:4.1f} bar  [{zone}]  agent left: {self.agent_left:.2f} kg"

    # -- PASS technique --------------------------------------------------
    def pull(self):
        self.pin_pulled = True
        print("  [P] Pin pulled - tamper seal broken.")

    def aim(self):
        if not self.pin_pulled:
            print("  ! Pull the pin first (P).")
            return False
        self.aimed = True
        print("  [A] Nozzle aimed at the BASE of the fire.")
        return True

    def squeeze_and_sweep(self, fire, distance_m, step_seconds=1.0, fast=False):
        """Discharge until the fire is out or the agent runs out. Returns True if extinguished."""
        if not (self.pin_pulled and self.aimed):
            print("  ! Complete Pull and Aim before squeezing.")
            return False

        # Compatibility check
        pair = (self.agent, fire.fire_class)
        if fire.fire_class in self.classes:
            effect = 1.0
        elif pair in DANGEROUS:
            effect = -0.5
            print(f"  !! DANGER: {DANGEROUS[pair]}")
        else:
            effect = 0.1
            print(f"  ! {self.agent} is not rated for Class {fire.fire_class}. Barely any effect.")

        if distance_m > self.range_m:
            effect *= 0.4
            print(f"  ! Too far ({distance_m} m). Effective range is {self.range_m} m - move closer.")

        print("  [S] Squeezing handle...  [S] Sweeping side to side at the base...")
        t = 0
        while not fire.is_out and self.agent_left > 0 and t < 30:
            t += 1
            used = min(self.rate_kg_s * step_seconds, self.agent_left)
            self.agent_left -= used
            sweep = random.uniform(0.85, 1.15)           # human sweep variation
            fire.grow(6 if effect <= 0 else 1.0)         # fire fights back (much more if agent is wrong)
            fire.apply(used * 32 * effect * sweep)       # 32 = heat removed per kg (model constant)
            print(f"      t={t:2d}s  fire heat: {fire.heat:5.1f}%   pressure: {self.pressure:4.1f} bar")
            if not fast:
                time.sleep(0.4)
        return fire.is_out


# --------------------------------------------------------------------------
# 4. Putting it together
# --------------------------------------------------------------------------
def ask_choice(prompt, options):
    while True:
        value = input(prompt).strip()
        if value.upper() in options or value.lower() in options:
            return value.upper() if value.upper() in options else value.lower()
        print(f"  Please choose one of: {', '.join(options)}")


def run(fire_class, agent, distance, auto, fast):
    fire = Fire(fire_class)
    print("\n" + "=" * 62)
    print(f" FIRE DETECTED -> Class {fire_class}: {FIRE_CLASSES[fire_class]}")
    print("=" * 62)

    if auto:
        agent = BEST_AGENT[fire_class]
        print(f" SMART MODE: flame sensor classified Class {fire_class}, selected '{agent}'.")

    ext = Extinguisher(agent)
    print(f" Extinguisher: {agent.upper()}  |  gauge: {ext.gauge()}")
    print(f" Rated for classes: {', '.join(sorted(ext.classes))}   |  range: {ext.range_m} m")
    print(f" You are standing {distance} m from the fire.\n")

    print(" Use the PASS technique:")
    if auto:
        ext.pull()
        ext.aim()
    else:
        steps = [("P", "Pull the pin", ext.pull), ("A", "Aim at the base", ext.aim)]
        for key, label, action in steps:
            while True:
                ask_choice(f"  Type {key} to '{label}': ", [key, key.lower()])
                if action() is not False:
                    break
        ask_choice("  Type S to 'Squeeze and Sweep': ", ["S", "s"])

    out = ext.squeeze_and_sweep(fire, distance, fast=fast)

    print("\n" + "-" * 62)
    if out:
        print(" RESULT: FIRE EXTINGUISHED. Keep watching for re-ignition and call the fire brigade (101 in India).")
    elif ext.agent_left <= 0:
        print(" RESULT: Extinguisher EMPTY and fire still burning. EVACUATE and call 101.")
    else:
        print(" RESULT: Fire NOT controlled. Leave the area, close the door, call 101.")
    print(f" Final gauge: {ext.gauge()}")
    print("-" * 62)


def main():
    parser = argparse.ArgumentParser(description="Fire extinguisher simulator")
    parser.add_argument("--fire", choices=list(FIRE_CLASSES), help="fire class")
    parser.add_argument("--agent", choices=list(AGENTS), help="extinguisher agent")
    parser.add_argument("--distance", type=float, default=2.0, help="distance from fire in metres")
    parser.add_argument("--auto", action="store_true", help="smart mode: auto pick agent + auto PASS")
    parser.add_argument("--fast", action="store_true", help="skip delays")
    args = parser.parse_args()

    fire_class = args.fire
    if not fire_class:
        print("Fire classes:")
        for k, v in FIRE_CLASSES.items():
            print(f"  {k}: {v}")
        fire_class = ask_choice("Choose fire class: ", list(FIRE_CLASSES))

    agent = args.agent
    if not agent and not args.auto:
        print("\nExtinguishers:", ", ".join(AGENTS))
        agent = ask_choice("Choose extinguisher: ", list(AGENTS))

    run(fire_class, agent, args.distance, args.auto, args.fast)


if __name__ == "__main__":
    main()
