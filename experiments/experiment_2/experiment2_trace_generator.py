import argparse
import random


def generate_trace(total_target_events: int) -> str:
    # Specification: EP(EP(a) & EP(b) & EP(c) & !EP(d))
    # Processes: PA, PB, PC, PD, PV (Verifier)
    # Phase 1 (Dormant): PA,PB,PC generate placeholder props (e.g., 'pa_active'). PD is quiet or placeholder.
    #                     No 'a','b','c','d' are generated. PV learns placeholder info.
    # Phase 2 (Active): After a threshold, processes start generating actual 'a','b','c','d'
    #                   with probabilities, and one later cycle is orchestrated for potential satisfaction.

    processes = ["PA", "PB", "PC", "PD", "PV"]
    system_processes_line = f"# system_processes: {'|'.join(processes)}\n"
    csv_header = "eid,processes,vc,props\n"
    trace_events = []

    current_vcs = {p: {other_p: 0 for other_p in processes} for p in processes}
    eid_counter = 0

    # --- Phase Control ---
    # Active phase starts after, e.g., 60% of events, but not before at least one full cycle can run in dormant.
    len_action_cycle = (
        9  # PA_int, PB_int, PC_int, PD_int, PA_PV, PB_PV, PC_PV, PD_PV, PV_decide
    )
    min_dormant_events = (
        len_action_cycle * 2
    )  # Ensure at least 2 full dormant cycles if possible

    activation_event_threshold = max(
        min_dormant_events, int(total_target_events * 0.60)
    )
    if (
        total_target_events <= len_action_cycle
    ):  # Very short trace, no real dormant phase
        activation_event_threshold = 0

    system_is_active_phase = False  # Flag to switch from dormant to active props

    # Orchestrated conclusive cycle (within active phase)
    start_of_orchestrated_cycle_event_num = -1
    if (
        total_target_events > activation_event_threshold + len_action_cycle * 1.5
    ):  # Enough space after activation
        min_orchestrated_start = activation_event_threshold + len_action_cycle // 2
        max_orchestrated_start = total_target_events - len_action_cycle - 1
        if max_orchestrated_start > min_orchestrated_start:
            start_of_orchestrated_cycle_event_num = random.randint(
                min_orchestrated_start, max_orchestrated_start
            )
            start_of_orchestrated_cycle_event_num -= (
                start_of_orchestrated_cycle_event_num % len_action_cycle
            )

    orchestrating_this_cycle = False
    orchestrated_cycle_action_counter = 0
    # --- End Phase Control ---

    props_at_source = {p: set() for p in ["PA", "PB", "PC", "PD"]}
    pv_learned_props_this_cycle = {p: set() for p in ["PA", "PB", "PC", "PD"]}
    pv_has_comm_from_pd_this_cycle = False

    action_sequence = [
        "PA_internal",
        "PB_internal",
        "PC_internal",
        "PD_internal",
        "PA_PV_comm",
        "PB_PV_comm",
        "PC_PV_comm",
        "PD_PV_comm",
        "PV_decide",
    ]
    action_idx = 0

    generated_events_count = 0
    while generated_events_count < total_target_events:
        # Determine if system transitions to active phase
        if (
            not system_is_active_phase
            and generated_events_count >= activation_event_threshold
        ):
            system_is_active_phase = True
            # Optional: Log an explicit "activation" event if desired (e.g., on PV)
            # For now, it's an implicit phase change.

        current_action_type = action_sequence[action_idx]
        action_occurred_this_step = False

        if (
            not orchestrating_this_cycle
            and system_is_active_phase
            and start_of_orchestrated_cycle_event_num != -1
            and generated_events_count >= start_of_orchestrated_cycle_event_num
            and action_idx == 0
        ):
            orchestrating_this_cycle = True
            orchestrated_cycle_action_counter = 0

        is_part_of_orchestrated_cycle = (
            orchestrating_this_cycle
            and orchestrated_cycle_action_counter < len_action_cycle
        )

        # --- Set Probabilities ---
        if is_part_of_orchestrated_cycle:  # Orchestrated TRUE attempt
            prob_prop_occurs = {"a": 0.95, "b": 0.95, "c": 0.95, "d": 0.01}
            prob_comm_happens = {"PA": 0.95, "PB": 0.95, "PC": 0.95, "PD": 0.05}
        elif system_is_active_phase:  # Active, but not orchestrated
            prob_prop_occurs = {"a": 0.6, "b": 0.6, "c": 0.6, "d": 0.3}
            prob_comm_happens = {"PA": 0.7, "PB": 0.7, "PC": 0.7, "PD": 0.4}
        else:  # Dormant phase
            prob_prop_occurs = {
                "a": 0.0,
                "b": 0.0,
                "c": 0.0,
                "d": 0.0,
            }  # Key props don't occur
            prob_comm_happens = {
                "PA": 0.3,
                "PB": 0.3,
                "PC": 0.3,
                "PD": 0.2,
            }  # Comms might happen but carry no key data

        event_process_field = ""
        event_props = set()
        event_vc_snapshot = {}
        event_eid_prefix = ""

        # --- Handle Actions ---
        if current_action_type.endswith("_internal"):
            proc_short_id = current_action_type[1]
            current_proc = f"P{proc_short_id}"
            prop_to_generate_letter = proc_short_id.lower()

            current_vcs[current_proc][current_proc] += 1
            props_at_source[current_proc] = set()

            if system_is_active_phase:  # Only generate a,b,c,d in active phase
                if random.random() < prob_prop_occurs.get(prop_to_generate_letter, 0.0):
                    props_at_source[current_proc].add(prop_to_generate_letter)
            else:  # Dormant phase, generate placeholder
                props_at_source[current_proc].add(
                    f"p{proc_short_id.lower()}_dormant_ping"
                )

            event_props.update(props_at_source[current_proc])
            event_vc_snapshot = current_vcs[current_proc].copy()
            event_process_field = current_proc
            event_eid_prefix = f"p{proc_short_id.lower()}_int"
            action_occurred_this_step = True

        elif current_action_type.endswith("_PV_comm"):
            sender_proc_short = current_action_type[1]
            sender_id = f"P{sender_proc_short}"

            current_prob_comm = prob_comm_happens.get(sender_id, 0.1)
            if (
                is_part_of_orchestrated_cycle and sender_id == "PD"
            ):  # Special handling for 'd' in orchestrated TRUE
                if "d" in props_at_source["PD"]:
                    current_prob_comm = 0.01
                else:
                    current_prob_comm = 0.95  # Communicate "no d"

            if random.random() < current_prob_comm:
                event_process_field = f"{sender_id}|PV"
                current_vcs[sender_id][sender_id] += 1
                current_vcs["PV"]["PV"] += 1
                merged_vc = {
                    k: max(
                        current_vcs[sender_id].get(k, 0), current_vcs["PV"].get(k, 0)
                    )
                    for k in set(current_vcs[sender_id]) | set(current_vcs["PV"])
                }
                current_vcs[sender_id] = merged_vc.copy()
                current_vcs["PV"] = merged_vc.copy()

                pv_learned_props_this_cycle[sender_id] = props_at_source[
                    sender_id
                ].copy()
                if sender_id == "PD":
                    pv_has_comm_from_pd_this_cycle = True

                event_props = {f"comm_{sender_id.lower()}_pv"}
                event_vc_snapshot = merged_vc.copy()
                event_eid_prefix = f"p{sender_proc_short.lower()}_pv_comm"
                action_occurred_this_step = True

        elif current_action_type == "PV_decide":
            event_process_field = "PV"
            current_vcs["PV"]["PV"] += 1

            if (
                system_is_active_phase
            ):  # PV only makes meaningful evaluations in active phase
                knows_a = "a" in pv_learned_props_this_cycle.get("PA", set())
                knows_b = "b" in pv_learned_props_this_cycle.get("PB", set())
                knows_c = "c" in pv_learned_props_this_cycle.get("PC", set())

                pv_thinks_d_is_false = False
                if not pv_has_comm_from_pd_this_cycle:
                    pv_thinks_d_is_false = True
                else:
                    if not ("d" in pv_learned_props_this_cycle.get("PD", set())):
                        pv_thinks_d_is_false = True

                if knows_a:
                    event_props.add("pv_knows_a")
                if knows_b:
                    event_props.add("pv_knows_b")
                if knows_c:
                    event_props.add("pv_knows_c")
                if pv_thinks_d_is_false:
                    event_props.add("pv_thinks_not_d")
                elif (
                    pv_has_comm_from_pd_this_cycle
                    and "d" in pv_learned_props_this_cycle.get("PD", set())
                ):
                    event_props.add("pv_knows_d_true")

            event_props.add("pv_eval_cycle_done")
            event_vc_snapshot = current_vcs["PV"].copy()
            event_eid_prefix = "pv_decide"
            action_occurred_this_step = True

            pv_learned_props_this_cycle = {p: set() for p in ["PA", "PB", "PC", "PD"]}
            pv_has_comm_from_pd_this_cycle = False
            if orchestrating_this_cycle:
                orchestrating_this_cycle = False
                orchestrated_cycle_action_counter = 0  # Reset

        if action_occurred_this_step:
            eid_counter += 1
            vc_str = ";".join(f"{p_clk}:{c}" for p_clk, c in event_vc_snapshot.items())
            props_str = "|".join(sorted(list(event_props))) if event_props else ""
            trace_events.append(
                f"{event_eid_prefix}{eid_counter},{event_process_field},{vc_str},{props_str}"
            )
            generated_events_count += 1

        action_idx = (action_idx + 1) % len_action_cycle
        if orchestrating_this_cycle:
            orchestrated_cycle_action_counter += 1
            if orchestrated_cycle_action_counter >= len_action_cycle:
                orchestrating_this_cycle = False

    return system_processes_line + csv_header + "\n".join(trace_events)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a trace for Exp 2 (Gatekeeper Phased): EP(EP(a) & EP(b) & EP(c) & !EP(d))."
    )
    parser.add_argument(
        "-s",
        "--size",
        type=int,
        required=True,
        help="Target total number of events to generate in the trace.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Path to the output CSV file. If not specified, prints to stdout.",
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
                    f"Trace for Experiment 2 (Gatekeeper Phased) successfully written to {args.output}"
                )
            except IOError as e:
                print(f"Error writing to file {args.output}: {e}")
        else:
            print(trace_data)
