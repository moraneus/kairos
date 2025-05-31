# Experiment 1: System Status Monitor

## 🎯 PBTL Property

`EP(status_ok & load_lt_100 & !critical_alarm)`

* **Type**: M-only (Existential Past of a conjunction of literals).
* **Goal**: The property is satisfied if there exists at least one global state (frontier) in the past execution where the system `status_ok` is true, the system `load_lt_100` (load is less than 100) is true, and there is no `critical_alarm`.
* **Interpretation**: This checks for a "good" operational snapshot in the system's history.

---

## ⚙️ Trace Generation (`experiment1_trace_generator.py`)

This script generates a CSV trace file simulating a distributed system with three processes, where their interactions and states are used to evaluate the property above.

### Processes and Roles:

* **S (Sensor)**: Monitors system load.
    * Generates internal events with propositions `load_lt_100` or `load_high`.
* **A (Actuator/Alarm Monitor)**: Monitors for critical alarms.
    * Generates internal events, potentially with the proposition `critical_alarm`.
* **M (Monitor)**: Aggregates information from S and A to determine overall system status.
    * Generates the `status_ok` proposition if its conditions (based on information from S and A) are met.

### Trace Construction and Communication Model:

The trace is constructed by cycling through a sequence of five logical actions. The `--size` parameter given to the script determines the total number of event lines in the output trace. Each action corresponds to one event in the trace:

1.  **S_internal**: Process `S` has an internal event (e.g., takes a load reading).
    * `processes`: `S`
    * `props`: `load_lt_100` or `load_high`.
    * `vc`: `S` increments its own clock component. The VC reflects `S`'s current state.
    * The generated propositions are stored internally by the generator for `M` to "learn" later.

2.  **A_internal**: Process `A` has an internal event (e.g., checks alarm status).
    * `processes`: `A`
    * `props`: `critical_alarm` (if an alarm is active), or empty.
    * `vc`: `A` increments its own clock component. The VC reflects `A`'s current state.
    * The generated propositions are stored internally by the generator for `M` to "learn" later.

3.  **SM_comm**: A shared/synchronous communication event between `S` and `M`.
    * `processes`: `S|M`
    * `props`: `s_m_comm` (to indicate the nature of the event).
    * `vc`:
        * `S` increments its clock component `S`.
        * `M` increments its clock component `M`.
        * Both `S`'s and `M`'s internal vector clocks are updated to be the component-wise maximum of their clocks. This merged VC is recorded for this event.
    * This event signifies that `M` now "knows" the state of `S` (specifically, `props_from_s_internal_for_m` which was set during `S_internal`).

4.  **AM_comm**: A shared/synchronous communication event between `A` and `M`.
    * `processes`: `A|M`
    * `props`: `a_m_comm`.
    * `vc`:
        * `A` increments its clock component `A`.
        * `M` increments its clock component `M` (again, following its previous update from `SM_comm`).
        * Both `A`'s and `M`'s internal vector clocks are updated to the component-wise maximum. This merged VC is recorded.
    * This event signifies that `M` now "knows" the state of `A` (specifically, `props_from_a_internal_for_m`).

5.  **M_decide**: Process `M` has an internal event to make its decision.
    * `processes`: `M`
    * `props`: Based on the information `M` learned from `S` (via `SM_comm`) and `A` (via `AM_comm`):
        * `load_lt_100` if `M` learned this from `S`.
        * `critical_alarm` if `M` learned this from `A`.
        * `status_ok` if `M` learned `load_lt_100` is true AND `critical_alarm` is false.
    * `vc`: `M` increments its own clock component. Its VC reflects its latest state, including knowledge gained from the communication events.

This cycle of 5 actions repeats. If `--size N` is given, `N` total events are generated, meaning the cycle repeats `N/5` times. The vector clocks are updated strictly according to the rules for internal events and shared/synchronous communication events, ensuring that knowledge propagation is explicitly tied to events where multiple processes participate and synchronize their clocks.