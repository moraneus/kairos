import argparse
import random


def generate_trace(total_target_events: int) -> str:
    # Property: EP( (EP(s1) & !EP(j1)) | (EP(j2) & ms & !EP(s2)) )
    # Processes: S1, J1, J2, MS, S2, PO (Observer)
    # Goal: Make conclusive verdict (TRUE/FALSE) more likely to occur
    #       in the 25-150 event window, not always at the very end or beginning.

    processes = ["S1", "J1", "J2", "MS", "S2", "PO"]
    system_processes_line = f"# system_processes: {'|'.join(processes)}\n"
    csv_header = "eid,processes,vc,props\n"
    trace_events = []

    current_vcs = {p: {other_p: 0 for other_p in processes} for p in processes}
    eid_counter = 0

    props_at_source = {p: set() for p in processes}
    po_learned_this_cycle = {p: set() for p in processes}
    po_learned_neg_cond_this_cycle = {"J1": False, "S2": False}

    s1, j1, j2, ms, s2 = "s1", "j1", "j2", "ms", "s2"
    dS1, dJ1, dJ2, dMS, dS2 = "dS1", "dJ1", "dJ2", "dMS", "dS2"
    cS1PO, cJ1PO, cJ2PO, cMSPO, cS2PO = "cS1PO", "cJ1PO", "cJ2PO", "cMSPO", "cS2PO"
    k_s1, k_j1, k_j2, k_ms, k_s2 = "kS1", "kJ1", "kJ2", "kMS", "kS2"
    poe = "poe"

    action_sequence = [
        "S1_internal",
        "J1_internal",
        "J2_internal",
        "MS_internal",
        "S2_internal",
        "S1_PO_comm",
        "J1_PO_comm",
        "J2_PO_comm",
        "MS_PO_comm",
        "S2_PO_comm",
        "PO_evaluate",
    ]
    action_idx = 0
    len_action_cycle = len(action_sequence)

    # --- Phase Control for Earlier Conclusive Verdict ---
    start_of_orchestrated_cycle_event_num = -1
    orchestrated_branch_target = None

    # Determine when the "active" phase (key props can be generated) begins.
    # Make it start fairly early to allow conclusion within 25-150 events.
    active_phase_start_threshold = 0
    if (
        total_target_events > len_action_cycle * 1.5
    ):  # if more than ~1.5 cycles, have a brief dormant
        active_phase_start_threshold = min(
            len_action_cycle, int(total_target_events * 0.1)
        )  # Start active phase quickly

    # Target the orchestrated cycle to be within 25-150 events if possible
    conclusive_window_start = 20  # Start trying a bit before 25
    conclusive_window_end = 150

    if total_target_events >= conclusive_window_start:
        # Calculate where the orchestrated cycle should start
        min_orc_start = max(
            active_phase_start_threshold, conclusive_window_start - len_action_cycle
        )
        max_orc_start = min(
            conclusive_window_end - len_action_cycle,
            total_target_events - len_action_cycle - 1,
        )

        if max_orc_start > min_orc_start:
            start_of_orchestrated_cycle_event_num = random.randint(
                min_orc_start, max_orc_start
            )
            start_of_orchestrated_cycle_event_num -= (
                start_of_orchestrated_cycle_event_num % len_action_cycle
            )
            orchestrated_branch_target = random.choice(["B1", "B2"])
        elif (
            total_target_events > len_action_cycle
        ):  # Fallback if window is too tight but trace is long enough for one cycle
            start_of_orchestrated_cycle_event_num = active_phase_start_threshold
            orchestrated_branch_target = random.choice(["B1", "B2"])

    orchestrating_this_cycle = False
    orchestrated_cycle_action_counter = 0
    # --- End Phase Control ---

    generated_events_count = 0
    while generated_events_count < total_target_events:
        current_action = action_sequence[action_idx]
        action_occurred_this_step = False

        system_is_active_phase = generated_events_count >= active_phase_start_threshold

        if (
            not orchestrating_this_cycle
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
        if is_part_of_orchestrated_cycle:
            if orchestrated_branch_target == "B1":
                prob_s1_occur, prob_comm_S1 = 0.90, 0.90
                prob_j1_occur, prob_comm_J1 = 0.10, 0.10
                prob_j2_occur, prob_ms_occur, prob_s2_occur = 0.05, 0.05, 0.8
                prob_comm_J2, prob_comm_MS, prob_comm_S2 = 0.05, 0.05, 0.05
            else:  # orchestrated_branch_target == "B2"
                prob_j2_occur, prob_comm_J2 = 0.90, 0.90
                prob_ms_occur, prob_comm_MS = 0.90, 0.90
                prob_s2_occur, prob_comm_S2 = 0.10, 0.10
                prob_s1_occur, prob_j1_occur, prob_comm_S1, prob_comm_J1 = (
                    0.05,
                    0.8,
                    0.05,
                    0.05,
                )
        elif system_is_active_phase:
            (
                prob_s1_occur,
                prob_j1_occur,
                prob_j2_occur,
                prob_ms_occur,
                prob_s2_occur,
            ) = (0.5, 0.4, 0.5, 0.4, 0.4)
            prob_comm_S1, prob_comm_J1, prob_comm_J2, prob_comm_MS, prob_comm_S2 = (
                0.5,
                0.5,
                0.5,
                0.5,
                0.5,
            )
        else:  # Dormant phase: key props do not occur
            (
                prob_s1_occur,
                prob_j1_occur,
                prob_j2_occur,
                prob_ms_occur,
                prob_s2_occur,
            ) = (0.0, 0.0, 0.0, 0.0, 0.0)
            prob_comm_S1, prob_comm_J1, prob_comm_J2, prob_comm_MS, prob_comm_S2 = (
                0.1,
                0.1,
                0.1,
                0.1,
                0.1,
            )

        event_process_field = ""
        event_props = set()
        event_vc_snapshot = {}
        event_eid_prefix = ""

        # --- Handle Actions ---
        if current_action.endswith("_internal"):
            proc_id = current_action.split("_")[0]
            current_vcs[proc_id][proc_id] += 1
            props_at_source[proc_id] = set()
            prop_to_add = None
            dormant_prop_to_add = None
            current_prob_occur = 0.0

            if proc_id == "S1":
                (
                    prop_to_add,
                    dormant_prop_to_add,
                    current_prob_occur,
                    event_eid_prefix,
                ) = (s1, dS1, prob_s1_occur, "s1_int")
            elif proc_id == "J1":
                (
                    prop_to_add,
                    dormant_prop_to_add,
                    current_prob_occur,
                    event_eid_prefix,
                ) = (j1, dJ1, prob_j1_occur, "j1_int")
            elif proc_id == "J2":
                (
                    prop_to_add,
                    dormant_prop_to_add,
                    current_prob_occur,
                    event_eid_prefix,
                ) = (j2, dJ2, prob_j2_occur, "j2_int")
            elif proc_id == "MS":
                event_eid_prefix = "ms_int"
                # MS depends on J2's prerequisite for 'ms'
                # In orchestrated B2, j2 is highly likely in po_learned_this_cycle.get("J2")
                # In other active phases, it's based on prior comm.
                j2_known_to_ms_or_orchestrated = (
                    "j2" in po_learned_this_cycle.get("J2", set())
                ) or (
                    is_part_of_orchestrated_cycle and orchestrated_branch_target == "B2"
                )
                if (
                    system_is_active_phase
                    and j2_known_to_ms_or_orchestrated
                    and random.random() < prob_ms_occur
                ):
                    prop_to_add = ms
                elif not system_is_active_phase:
                    dormant_prop_to_add = dMS
            elif proc_id == "S2":
                (
                    prop_to_add,
                    dormant_prop_to_add,
                    current_prob_occur,
                    event_eid_prefix,
                ) = (s2, dS2, prob_s2_occur, "s2_int")

            if (
                prop_to_add
                and system_is_active_phase
                and random.random() < current_prob_occur
            ):
                props_at_source[proc_id].add(prop_to_add)
            elif (
                dormant_prop_to_add and not system_is_active_phase
            ):  # Only add dormant if not active phase for key props
                props_at_source[proc_id].add(dormant_prop_to_add)

            event_props.update(props_at_source[proc_id])
            event_vc_snapshot = current_vcs[proc_id].copy()
            event_process_field = proc_id
            action_occurred_this_step = True

        elif current_action.endswith("_PO_comm"):
            sender_id = current_action.split("_")[0]
            prob_this_comm = locals().get(f"prob_comm_{sender_id}", 0.1)

            if (
                is_part_of_orchestrated_cycle
            ):  # Adjust comm probability for negative conditions during orchestration
                if (
                    orchestrated_branch_target == "B1"
                    and sender_id == "J1"
                    and j1 in props_at_source["J1"]
                ):
                    prob_this_comm = 0.01  # Suppress j1 communication if it occurred
                elif (
                    orchestrated_branch_target == "B2"
                    and sender_id == "S2"
                    and s2 in props_at_source["S2"]
                ):
                    prob_this_comm = 0.01  # Suppress s2 communication if it occurred

            if random.random() < prob_this_comm:
                event_process_field = f"{sender_id}|PO"
                current_vcs[sender_id][sender_id] += 1
                current_vcs["PO"]["PO"] += 1
                merged_vc = {
                    k: max(
                        current_vcs[sender_id].get(k, 0), current_vcs["PO"].get(k, 0)
                    )
                    for k in set(current_vcs[sender_id]) | set(current_vcs["PO"])
                }
                current_vcs[sender_id] = merged_vc.copy()
                current_vcs["PO"] = merged_vc.copy()
                po_learned_this_cycle[sender_id] = props_at_source[sender_id].copy()
                if sender_id == "J1" and j1 in po_learned_this_cycle[sender_id]:
                    po_learned_neg_cond_this_cycle["J1"] = True
                if sender_id == "S2" and s2 in po_learned_this_cycle[sender_id]:
                    po_learned_neg_cond_this_cycle["S2"] = True
                event_props = {
                    locals().get(f"c{sender_id}PO", f"comm_{sender_id.lower()}_po")
                }
                event_vc_snapshot = merged_vc.copy()
                event_eid_prefix = f"{sender_id.lower()}_po_comm"
                action_occurred_this_step = True

        elif current_action == "PO_evaluate":
            event_process_field = "PO"
            current_vcs["PO"]["PO"] += 1
            if system_is_active_phase:
                knows_s1 = s1 in po_learned_this_cycle.get("S1", set())
                not_knows_j1 = not po_learned_neg_cond_this_cycle["J1"]
                knows_j2 = j2 in po_learned_this_cycle.get("J2", set())
                knows_ms = ms in po_learned_this_cycle.get("MS", set())
                not_knows_s2 = not po_learned_neg_cond_this_cycle["S2"]

                if knows_s1:
                    event_props.add(k_s1)
                if not_knows_j1:
                    event_props.add("k_not_j1")
                elif po_learned_neg_cond_this_cycle["J1"]:
                    event_props.add(k_j1)
                if knows_j2:
                    event_props.add(k_j2)
                if knows_ms:
                    event_props.add(k_ms)
                if not_knows_s2:
                    event_props.add("k_not_s2")
                elif po_learned_neg_cond_this_cycle["S2"]:
                    event_props.add(k_s2)
            event_props.add(poe)
            event_vc_snapshot = current_vcs["PO"].copy()
            event_eid_prefix = "po_eval"
            action_occurred_this_step = True
            po_learned_this_cycle = {p: set() for p in processes}
            po_learned_neg_cond_this_cycle = {"J1": False, "S2": False}
            if orchestrating_this_cycle:
                orchestrating_this_cycle = False

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
        description="Generate a trace for Exp 4 (Disjunction, conclusive 25-150 events): EP((s1 & !EP(j1)) | ... )."
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
                    f"Trace for Experiment 4 (conclusive 25-150) written to {args.output}"
                )
            except IOError as e:
                print(f"Error writing to file {args.output}: {e}")
        else:
            print(trace_data)
