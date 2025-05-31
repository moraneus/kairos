import argparse
import random


def generate_trace(total_target_events: int) -> str:
    # Specification: EP( (aX & EP(pX)) | (aY & EP(pY)) )
    # Processes: PX (handles pathway X), PY (handles pathway Y), PV (Verifier)
    # Goal: Delay conclusive verdict. Orchestrate satisfaction of one branch
    #       (either X or Y) late in the trace. Uses short proposition names.

    processes = ["PX", "PY", "PV"]
    system_processes_line = f"# system_processes: {'|'.join(processes)}\n"
    csv_header = "eid,processes,vc,props\n"
    trace_events = []

    current_vcs = {p: {other_p: 0 for other_p in processes} for p in processes}
    eid_counter = 0

    # Store current state of props at source (PX, PY) after their internal events
    props_at_source = {"PX": set(), "PY": set()}

    # What PV has learned in its current "observation window" from PX and PY
    pv_learned_from_px = set()
    pv_learned_from_py = set()

    # Define short prop names
    pX, aX, pY, aY = "pX", "aX", "pY", "aY"  # Key props for the property
    dX, dY = "dX", "dY"  # Dormant/placeholder props
    cXP, cYP = "cXP", "cYP"  # Communication event markers
    kvpX, kvaX, kvpY, kvaY, pve = (
        "kvpX",
        "kvaX",
        "kvpY",
        "kvaY",
        "pve",
    )  # PV 'knows'/'evaluates' props

    # Logical action sequence for one cycle of PX, PY, and PV evaluation
    action_sequence = [
        "PX_prereq_internal",
        "PX_action_internal",
        "PY_prereq_internal",
        "PY_action_internal",
        "PX_PV_comm",
        "PY_PV_comm",
        "PV_evaluate",
    ]
    action_idx = 0
    len_action_cycle = len(action_sequence)

    # --- Phase Control for Delayed Conclusion ---
    start_of_orchestrated_cycle_event_num = -1
    orchestrated_branch_target = None  # Will be "X" or "Y"

    # Determine when the "active" phase (where key props can be generated) begins
    # Allow at least one full dormant cycle if trace is long enough.
    active_phase_start_threshold = len_action_cycle
    if total_target_events <= len_action_cycle * 2:  # If trace is very short
        active_phase_start_threshold = 0  # Make it active from start

    # Determine when the single "orchestrated conclusive cycle" should start, within the active phase.
    if (
        total_target_events > active_phase_start_threshold + len_action_cycle * 1.5
    ):  # Enough space for orchestration
        min_orchestrated_start = active_phase_start_threshold + random.randint(
            0, int(len_action_cycle * 0.5)
        )
        # Ensure orchestration happens in the latter half if possible, but after activation
        min_orchestrated_start = max(
            min_orchestrated_start, int(total_target_events * 0.6)
        )

        max_orchestrated_start = total_target_events - len_action_cycle - 1

        if max_orchestrated_start > min_orchestrated_start:
            # Pick a random start for the orchestrated cycle's first action
            start_of_orchestrated_cycle_event_num = random.randint(
                min_orchestrated_start, max_orchestrated_start
            )
            # Align it to the beginning of an action_sequence cycle
            start_of_orchestrated_cycle_event_num -= (
                start_of_orchestrated_cycle_event_num % len_action_cycle
            )
            orchestrated_branch_target = random.choice(["X", "Y"])

    orchestrating_this_cycle_now = (
        False  # Flag if current events are part of this special cycle
    )
    orchestrated_cycle_current_action_count = 0
    # --- End Phase Control ---

    generated_events_count = 0
    while generated_events_count < total_target_events:
        current_action = action_sequence[action_idx]
        action_occurred_this_step = (
            False  # Flag to ensure event counter increments only for actual events
        )

        system_is_in_active_phase = (
            generated_events_count >= active_phase_start_threshold
        )

        # Check if we are starting or continuing an orchestrated cycle
        if (
            not orchestrating_this_cycle_now
            and system_is_in_active_phase
            and start_of_orchestrated_cycle_event_num != -1
            and generated_events_count >= start_of_orchestrated_cycle_event_num
            and action_idx == 0
        ):  # Orchestration starts at the beginning of an action cycle
            orchestrating_this_cycle_now = True
            orchestrated_cycle_current_action_count = 0

        is_currently_orchestrated_action = (
            orchestrating_this_cycle_now
            and orchestrated_cycle_current_action_count < len_action_cycle
        )

        # --- Set Probabilities based on current phase ---
        if is_currently_orchestrated_action:
            if orchestrated_branch_target == "X":
                prob_pX_occur, prob_aX_occur, prob_comm_PX = (
                    0.95,
                    0.95,
                    0.95,
                )  # High for target branch X
                prob_pY_occur, prob_aY_occur, prob_comm_PY = (
                    0.05,
                    0.05,
                    0.05,
                )  # Low for other branch Y
            else:  # orchestrated_branch_target == "Y"
                prob_pY_occur, prob_aY_occur, prob_comm_PY = (
                    0.95,
                    0.95,
                    0.95,
                )  # High for target branch Y
                prob_pX_occur, prob_aX_occur, prob_comm_PX = (
                    0.05,
                    0.05,
                    0.05,
                )  # Low for other branch X
        elif system_is_in_active_phase:
            # Active but not orchestrated: moderate chances, still somewhat hard to align
            prob_pX_occur, prob_aX_occur, prob_pY_occur, prob_aY_occur = (
                0.4,
                0.3,
                0.4,
                0.3,
            )
            prob_comm_PX, prob_comm_PY = 0.3, 0.3
        else:  # Dormant phase: key props (pX, aX, pY, aY) do not occur
            prob_pX_occur, prob_aX_occur, prob_pY_occur, prob_aY_occur = (
                0.0,
                0.0,
                0.0,
                0.0,
            )
            prob_comm_PX, prob_comm_PY = (
                0.15,
                0.15,
            )  # Low chance of communicating dormant pings

        event_process_field = ""
        event_props = set()
        event_vc_snapshot = {}
        event_eid_prefix = ""

        # --- Handle Actions ---
        if current_action == "PX_prereq_internal":
            event_process_field = "PX"
            current_vcs["PX"]["PX"] += 1
            props_at_source["PX"].clear()
            if system_is_in_active_phase and random.random() < prob_pX_occur:
                props_at_source["PX"].add(pX)
            elif not system_is_in_active_phase:
                props_at_source["PX"].add(dX)
            event_props.update(props_at_source["PX"])
            event_vc_snapshot = current_vcs["PX"].copy()
            event_eid_prefix = "px_pre"
            action_occurred_this_step = True

        elif current_action == "PX_action_internal":
            event_process_field = "PX"
            current_vcs["PX"]["PX"] += 1
            # Action X only if its prereq pX was set in PX's current internal state (from PX_prereq)
            if system_is_in_active_phase and pX in props_at_source["PX"]:
                if random.random() < prob_aX_occur:
                    props_at_source["PX"].add(aX)
            # props_at_source["PX"] carries over pX if it was set
            event_props.update(props_at_source["PX"])
            event_vc_snapshot = current_vcs["PX"].copy()
            event_eid_prefix = "px_act"
            action_occurred_this_step = True

        elif current_action == "PY_prereq_internal":
            event_process_field = "PY"
            current_vcs["PY"]["PY"] += 1
            props_at_source["PY"].clear()
            if system_is_in_active_phase and random.random() < prob_pY_occur:
                props_at_source["PY"].add(pY)
            elif not system_is_in_active_phase:
                props_at_source["PY"].add(dY)
            event_props.update(props_at_source["PY"])
            event_vc_snapshot = current_vcs["PY"].copy()
            event_eid_prefix = "py_pre"
            action_occurred_this_step = True

        elif current_action == "PY_action_internal":
            event_process_field = "PY"
            current_vcs["PY"]["PY"] += 1
            if system_is_in_active_phase and pY in props_at_source["PY"]:
                if random.random() < prob_aY_occur:
                    props_at_source["PY"].add(aY)
            event_props.update(props_at_source["PY"])
            event_vc_snapshot = current_vcs["PY"].copy()
            event_eid_prefix = "py_act"
            action_occurred_this_step = True

        elif current_action == "PX_PV_comm":
            if random.random() < prob_comm_PX:  # Communication is probabilistic
                event_process_field = "PX|PV"
                current_vcs["PX"]["PX"] += 1
                current_vcs["PV"]["PV"] += 1
                merged_vc = {
                    k: max(current_vcs["PX"].get(k, 0), current_vcs["PV"].get(k, 0))
                    for k in set(current_vcs["PX"]) | set(current_vcs["PV"])
                }
                current_vcs["PX"] = merged_vc.copy()
                current_vcs["PV"] = merged_vc.copy()
                pv_learned_from_px = props_at_source[
                    "PX"
                ].copy()  # PV learns PX's last internal state
                event_props = {cXP}
                event_vc_snapshot = merged_vc.copy()
                event_eid_prefix = "pxpv_comm"
                action_occurred_this_step = True
            # else: communication skipped

        elif current_action == "PY_PV_comm":
            if random.random() < prob_comm_PY:  # Communication is probabilistic
                event_process_field = "PY|PV"
                current_vcs["PY"]["PY"] += 1
                current_vcs["PV"]["PV"] += 1
                merged_vc = {
                    k: max(current_vcs["PY"].get(k, 0), current_vcs["PV"].get(k, 0))
                    for k in set(current_vcs["PY"]) | set(current_vcs["PV"])
                }
                current_vcs["PY"] = merged_vc.copy()
                current_vcs["PV"] = merged_vc.copy()
                pv_learned_from_py = props_at_source["PY"].copy()
                event_props = {cYP}
                event_vc_snapshot = merged_vc.copy()
                event_eid_prefix = "pypv_comm"
                action_occurred_this_step = True
            # else: communication skipped

        elif current_action == "PV_evaluate":
            event_process_field = "PV"
            current_vcs["PV"]["PV"] += 1
            # Add props to PV event reflecting what it learned in this logical cycle
            if pX in pv_learned_from_px:
                event_props.add(kvpX)
            if aX in pv_learned_from_px:
                event_props.add(kvaX)
            if pY in pv_learned_from_py:
                event_props.add(kvpY)
            if aY in pv_learned_from_py:
                event_props.add(kvaY)
            event_props.add(pve)
            event_vc_snapshot = current_vcs["PV"].copy()
            event_eid_prefix = "pv_eval"
            action_occurred_this_step = True

            # Reset PV's knowledge for the next logical cycle and end orchestration if it was active
            pv_learned_from_px = set()
            pv_learned_from_py = set()
            if (
                orchestrating_this_cycle_now
            ):  # This PV_evaluate ends the current orchestrated cycle
                orchestrating_this_cycle_now = False

        if action_occurred_this_step:
            eid_counter += 1
            vc_str = ";".join(f"{p_clk}:{c}" for p_clk, c in event_vc_snapshot.items())
            props_str = "|".join(sorted(list(event_props))) if event_props else ""
            trace_events.append(
                f"{event_eid_prefix}{eid_counter},{event_process_field},{vc_str},{props_str}"
            )
            generated_events_count += 1

        action_idx = (action_idx + 1) % len_action_cycle
        if orchestrating_this_cycle_now:  # Increment counter for orchestrated cycle
            orchestrated_cycle_current_action_count += 1
            if orchestrated_cycle_current_action_count >= len_action_cycle:
                orchestrating_this_cycle_now = (
                    False  # Ensure it only lasts one cycle's worth of actions
                )

    return system_processes_line + csv_header + "\n".join(trace_events)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a trace for Exp 3 (Conditional Action, Short Props, Delayed): "
        "EP((aX & EP(pX)) | (aY & EP(pY)))."
    )
    parser.add_argument(
        "-s",
        "--size",
        type=int,
        required=True,
        help="Target total number of events to generate.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output CSV file path. Prints to stdout if not specified.",
    )
    args = parser.parse_args()
    if args.size <= 0:
        print("Error: Size must be a positive integer.")
    else:
        trace_data = generate_trace(args.size)
        if args.output:
            try:
                with open(args.output, "w") as f:
                    f.write(trace_data)
                print(
                    f"Trace for Experiment 3 (Conditional, Short Props, Delayed) written to {args.output}"
                )
            except IOError as e:
                print(f"Error writing to file {args.output}: {e}")
        else:
            print(trace_data)
