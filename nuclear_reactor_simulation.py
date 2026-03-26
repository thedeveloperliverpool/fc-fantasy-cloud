"""
Educational nuclear fission reactor simulation.

This is a simplified point-kinetics style model intended for learning,
not for engineering design or operational use.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReactorState:
    time_s: float
    neutron_population: float
    fuel_temperature_c: float
    coolant_temperature_c: float
    control_rod_insertion: float  # 0.0 = fully withdrawn, 1.0 = fully inserted
    thermal_power_mw: float


class ReactorSimulator:
    """
    Simple educational reactor model.

    Model intuition:
    - Neutrons cause fission events.
    - More neutrons => more fissions => more power.
    - Control rods absorb neutrons and reduce the chain reaction.
    - Higher fuel temperature creates negative reactivity feedback.
    """

    # Tunable constants for educational behavior (not physical plant values)
    BASE_REACTIVITY = 0.035
    ROD_WORTH = 0.06
    TEMP_FEEDBACK_PER_C = 0.00012
    FUEL_HEAT_CAPACITY = 30.0
    COOLANT_HEAT_CAPACITY = 60.0
    HEAT_TRANSFER_RATE = 0.08
    COOLING_RATE = 0.05
    AMBIENT_TEMP_C = 25.0
    POWER_SCALE = 1800.0

    def __init__(self) -> None:
        self.state = ReactorState(
            time_s=0.0,
            neutron_population=1.0,
            fuel_temperature_c=280.0,
            coolant_temperature_c=260.0,
            control_rod_insertion=0.80,
            thermal_power_mw=0.0,
        )

    def set_control_rod_insertion(self, insertion: float) -> None:
        self.state.control_rod_insertion = max(0.0, min(1.0, insertion))

    def _reactivity(self) -> float:
        # Negative temperature feedback (higher temperature lowers reactivity)
        temp_feedback = self.TEMP_FEEDBACK_PER_C * (self.state.fuel_temperature_c - 280.0)
        rod_absorption = self.ROD_WORTH * self.state.control_rod_insertion
        return self.BASE_REACTIVITY - rod_absorption - temp_feedback

    def step(self, dt: float) -> ReactorState:
        k = self._reactivity()

        # Neutron population evolution (simplified exponential growth/decay)
        growth = 1.0 + k * dt
        growth = max(0.01, growth)
        self.state.neutron_population *= growth

        # Prevent runaway in this toy model for readable output
        self.state.neutron_population = min(self.state.neutron_population, 25.0)

        self.state.thermal_power_mw = self.state.neutron_population * self.POWER_SCALE

        # Fuel heats from fission power and cools by transferring heat to coolant
        heating = self.state.thermal_power_mw / self.FUEL_HEAT_CAPACITY
        transfer_to_coolant = (
            (self.state.fuel_temperature_c - self.state.coolant_temperature_c)
            * self.HEAT_TRANSFER_RATE
        )
        self.state.fuel_temperature_c += (heating - transfer_to_coolant) * dt

        # Coolant receives heat from fuel and dumps heat to environment
        coolant_loss = (
            (self.state.coolant_temperature_c - self.AMBIENT_TEMP_C) * self.COOLING_RATE
        )
        self.state.coolant_temperature_c += (transfer_to_coolant - coolant_loss) * dt

        self.state.time_s += dt
        return self.state


def run_demo() -> None:
    reactor = ReactorSimulator()
    dt = 1.0

    print("Nuclear Reactor Simulation (educational)")
    print(
        "time(s) | rods(%) | neutrons | power(MWth) | fuel(C) | coolant(C)"
    )
    print("-" * 68)

    for _ in range(180):
        t = reactor.state.time_s

        # Startup: gradually withdraw rods to raise power
        if t < 40:
            reactor.set_control_rod_insertion(0.80 - (t / 40.0) * 0.40)
        # Power hold: near-critical control
        elif t < 120:
            reactor.set_control_rod_insertion(0.40)
        # Shutdown: insert rods to reduce reaction
        else:
            reactor.set_control_rod_insertion(0.90)

        state = reactor.step(dt)

        if int(state.time_s) % 10 == 0:
            print(
                f"{state.time_s:6.0f} |"
                f" {state.control_rod_insertion * 100:6.1f} |"
                f" {state.neutron_population:8.3f} |"
                f" {state.thermal_power_mw:10.1f} |"
                f" {state.fuel_temperature_c:7.1f} |"
                f" {state.coolant_temperature_c:10.1f}"
            )


if __name__ == "__main__":
    run_demo()
