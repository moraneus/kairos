# Experiment 2: Multi-Condition Past Verification

## 🎯 PBTL Property

`EP(EP(a) & EP(b) & EP(c) & !EP(d))`

* **Type**: This property involves nested `EP` operators (P-blocks for `a`, `b`, `c`) and a negated `EP` operator (an N-block for `d`).
* **Goal**: The property is satisfied if there exists a past global state (frontier) where, from the perspective of that frontier:
    * `EP(a)`: Proposition `a` has held at some point in its causal past.
    * `EP(b)`: Proposition `b` has held at some point in its causal past.
    * `EP(c)`: Proposition `c` has held at some point in its causal past.
    * `!EP(d)`: Proposition `d` has *not* held at any point in its causal past (up to or concurrent with the satisfying frontier).
* **Interpretation**: This checks for a state where three prerequisite conditions (`a`, `b`, `c`) have been met historically, and a fourth, undesirable condition (`d`), has *not* been established in the relevant history.

---

## ⚙️ Trace Generation (`experiment2_trace_generator.py`)

This script generates a CSV trace file simulating a distributed system with five processes. The trace is constructed to make the satisfaction or definitive violation of the property less likely to occur at the beginning, introducing phases to control when key propositions are generated and communicated.

### Processes and Roles:

* **PA, PB, PC**: These processes are responsible for eventually generating the prerequisite propositions `a`, `b`, and `c`, respectively, through internal events.
* **PD**: This process may eventually generate the proposition `d` (which is undesirable for the property's satisfaction) through an internal event.
* **PV (Verifier)**: This process "observes" or learns about the states of PA, PB, PC, and PD through shared/synchronous communication events. The property's truth is evaluated based on PV's accumulated knowledge.

### Trace Construction and Communication Model:

The trace generation adheres to the `--size` parameter for the total number of events. It cycles through a defined sequence of logical actions, with behavior changing based on phases:

1.  **Phased Proposition Generation**:
    * **Dormant Phase (e.g., first ~60% of events, or a minimum number of initial cycles)**:
        * PA, PB, PC: Do *not* generate their key props (`a`,`b`,`c`). Instead, they might generate placeholder props (e.g., `pa_dormant_ping`).
        * PD: Does *not* generate `d`. Might generate a placeholder like `pd_dormant_ping`.
        * Communication events between these processes and PV still occur based on their turn in the action cycle but will only transfer these placeholder/neutral props.
        * This phase ensures that the conditions for the property (`a,b,c` true, `d` false from PV's perspective) cannot be met early on, keeping the monitor likely `INCONCLUSIVE`.
    * **Active Phase (remaining events after the `activation_event_threshold`)**:
        * PA, PB, PC: Start generating their respective props (`a`,`b`,`c`) based on defined (but still somewhat random) probabilities.
        * PD: Starts generating `d` based on its defined probability.
        * Communication with PV now involves these actual props.

2.  **Orchestrated Conclusive Cycle (within the Active Phase)**:
    * A single logical cycle (from PA_internal through PV_decide) occurring late in the trace (e.g., between 65-85% of total events, if the trace is long enough) is "orchestrated."
    * **During this specific cycle**:
        * The probabilities for `a,b,c` occurring at their source and being successfully communicated to PV are set very high.
        * The probability for `d` occurring at PD is set very low.
        * If `d` *does* occur by chance, the probability of it being communicated to PV during this orchestrated cycle is made extremely low. The goal is for PV to confirm "no `d`" (either because `d` didn't happen or PD communicated its absence).
    * This creates a high likelihood (but not a guarantee) that PV will see the conditions for a `TRUE` verdict during this specific cycle.
    * Outside this single orchestrated cycle (both before in the active phase, and after it), the probabilities for `a,b,c,d` and their communications are more moderate or less favorable, making spontaneous satisfaction less likely.

3.  **Logical Action Cycle**: The generator iterates through a sequence of actions for each event:
    * **`PX_internal`** (X being A, B, C, or D): The source process has an internal event.
        * `processes`: Single process (e.g., `PA`).
        * `props`: In dormant phase, placeholder (e.g., `pa_dormant_ping`). In active phase, `a`, `b`, `c`, or `d` (based on probabilities and whether it's the orchestrated cycle).
        * `vc`: The process increments its own clock component.
        * The generated props are stored by the generator for potential "transfer" during a communication event.
    * **`PX_PV_comm`** (X being A, B, C, or D): A shared/synchronous communication event.
        * `processes`: Two processes (e.g., `PA|PV`).
        * `props`: A communication marker (e.g., `comm_pa_pv`).
        * `vc`: Both the sender (`PX`) and `PV` increment their respective clock components. Their internal vector clocks are then updated to the component-wise maximum of their two clocks. This merged VC is recorded for the event.
        * This event signifies that `PV` now "knows" the state/props of `PX` from `PX`'s last internal event. The probability of this communication occurring is phase-dependent.
    * **`PV_decide`**: Process `PV` has an internal event.
        * `processes`: `PV`.
        * `props`: Reflects PV's current knowledge (e.g., `pv_knows_a`, `pv_thinks_not_d`).
        * `vc`: `PV` increments its own clock component.
        * Internal state tracking PV's knowledge for the current logical cycle is reset.

4.  **Total Event Count**: The main loop runs to generate exactly the number of events specified by the `--size` argument. If a probabilistic action (like a communication event) is skipped, the generator moves to the next action in the cycle but ensures the total count of *actual generated events* meets the target.

This multi-phase approach with an orchestrated late cycle is designed to produce traces where conclusive verdicts are deliberately delayed, providing a more challenging scenario for the runtime monitor.