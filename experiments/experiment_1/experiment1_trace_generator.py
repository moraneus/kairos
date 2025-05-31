import argparse
import random


def generate_trace(total_target_events: int) -> str:
    # Specification: EP(status_ok & load_lt_100 & !critical_alarm)
    # Processes:
    #   S (Sensor): Generates 'load_lt_100' or 'load_high'.
    #   A (Actuator): May generate 'critical_alarm'.
    #   M (Monitor): Assesses system state.
    # Communication is modeled as shared/synchronous events.

    processes = ["M", "S", "A"]  # Monitor, Sensor, Actuator
    system_processes_line = f"# system_processes: {'|'.join(processes)}\n"
    csv_header = "eid,processes,vc,props\n"
    trace_events = []

    current_vcs = {p: {other_p: 0 for other_p in processes} for p in processes}
    eid_counter = 0

    # Store props and VCs from internal events to be "transferred"
    # These represent the *data* M will eventually learn and the VC of the event where S/A generated that data
    props_from_s_internal_for_m = {"load_high"}
    vc_of_s_internal_data_event = current_vcs["S"].copy()

    props_from_a_internal_for_m = {
        "critical_alarm"
    }  # Start with alarm active to delay status_ok
    vc_of_a_internal_data_event = current_vcs["A"].copy()

    # Track if M has "fresh" data from S and A since the last M_decide
    m_has_fresh_s_data = False
    m_has_fresh_a_data = False

    action_sequence = [
        ("S_internal"),
        ("A_internal"),
        ("SM_comm"),
        ("AM_comm"),
        ("M_decide"),
    ]
    action_idx = 0

    # Probabilities for "good" states
    prob_load_lt_100 = 0.4  # Sensor reports load_lt_100 less often
    prob_no_critical_alarm = (
        0.6  # Actuator reports no critical_alarm more often, but not always
    )

    for _ in range(total_target_events):
        eid_counter += 1
        current_action = action_sequence[action_idx]
        action_idx = (action_idx + 1) % len(action_sequence)

        event_process_field = ""
        event_props = set()
        event_vc_snapshot = {}
        event_eid_prefix = ""

        if current_action == "S_internal":
            event_process_field = "S"
            current_vcs["S"]["S"] += 1
            if random.random() < prob_load_lt_100:
                props_s_internal = {"load_lt_100"}
            else:
                props_s_internal = {"load_high"}
            event_props.update(props_s_internal)
            props_from_s_internal_for_m = props_s_internal.copy()
            vc_of_s_internal_data_event = current_vcs[
                "S"
            ].copy()  # VC of this specific S_internal event
            event_vc_snapshot = current_vcs["S"].copy()
            event_eid_prefix = "s_int"

        elif current_action == "A_internal":
            event_process_field = "A"
            current_vcs["A"]["A"] += 1
            props_a_internal = set()
            if not (
                random.random() < prob_no_critical_alarm
            ):  # More likely to have an alarm initially
                props_a_internal.add("critical_alarm")
            event_props.update(props_a_internal)
            props_from_a_internal_for_m = props_a_internal.copy()
            vc_of_a_internal_data_event = current_vcs[
                "A"
            ].copy()  # VC of this specific A_internal event
            event_vc_snapshot = current_vcs["A"].copy()
            event_eid_prefix = "a_int"

        elif current_action == "SM_comm":
            event_process_field = "S|M"
            current_vcs["S"]["S"] += 1
            current_vcs["M"]["M"] += 1
            merged_vc_sm = {
                k: max(current_vcs["S"].get(k, 0), current_vcs["M"].get(k, 0))
                for k in set(current_vcs["S"]) | set(current_vcs["M"])
            }
            current_vcs["S"] = merged_vc_sm.copy()
            current_vcs["M"] = merged_vc_sm.copy()
            event_props = {"s_m_comm"}
            m_has_fresh_s_data = True  # M now has (conceptually) the latest from S
            event_vc_snapshot = merged_vc_sm.copy()
            event_eid_prefix = "sm_comm"

        elif current_action == "AM_comm":
            event_process_field = "A|M"
            current_vcs["A"]["A"] += 1
            current_vcs["M"]["M"] += 1
            merged_vc_am = {
                k: max(current_vcs["A"].get(k, 0), current_vcs["M"].get(k, 0))
                for k in set(current_vcs["A"]) | set(current_vcs["M"])
            }
            current_vcs["A"] = merged_vc_am.copy()
            current_vcs["M"] = merged_vc_am.copy()
            event_props = {"a_m_comm"}
            m_has_fresh_a_data = True  # M now has (conceptually) the latest from A
            event_vc_snapshot = merged_vc_am.copy()
            event_eid_prefix = "am_comm"

        elif current_action == "M_decide":
            event_process_field = "M"
            current_vcs["M"]["M"] += 1

            # M can only make an informed decision if it has received fresh data from both
            if m_has_fresh_s_data and m_has_fresh_a_data:
                # Check if M's current VC reflects knowledge of the specific S and A internal events
                # whose props are stored in props_from_s_internal_for_m / props_from_a_internal_for_m
                m_knows_s_data_event = all(
                    current_vcs["M"].get(p, 0) >= clk
                    for p, clk in vc_of_s_internal_data_event.items()
                )
                m_knows_a_data_event = all(
                    current_vcs["M"].get(p, 0) >= clk
                    for p, clk in vc_of_a_internal_data_event.items()
                )

                if m_knows_s_data_event and m_knows_a_data_event:
                    known_load_lt_100 = "load_lt_100" in props_from_s_internal_for_m
                    known_critical_alarm = (
                        "critical_alarm" in props_from_a_internal_for_m
                    )

                    if known_load_lt_100:
                        event_props.add("load_lt_100")
                    if known_critical_alarm:
                        event_props.add("critical_alarm")

                    # Only set status_ok if conditions are ideal and data is fresh
                    if known_load_lt_100 and not known_critical_alarm:
                        # Delay status_ok further by making it probabilistic even if conditions are met
                        if (
                            random.random() < 0.25
                        ):  # status_ok only 25% of the time conditions are perfect
                            event_props.add("status_ok")
                else:
                    event_props.add(
                        "m_awaits_data_sync"
                    )  # M decided but didn't have full causal knowledge

                # Reset fresh data flags after a decision attempt based on them
                m_has_fresh_s_data = False
                m_has_fresh_a_data = False
            else:
                event_props.add(
                    "m_awaits_updates"
                )  # M decided without fresh data from both S and A

            event_vc_snapshot = current_vcs["M"].copy()
            event_eid_prefix = "m_decide"

        vc_str = ";".join(f"{p}:{c}" for p, c in event_vc_snapshot.items())
        props_str = "|".join(sorted(list(event_props))) if event_props else ""
        trace_events.append(
            f"{event_eid_prefix}{eid_counter},{event_process_field},{vc_str},{props_str}"
        )

    return system_processes_line + csv_header + "\n".join(trace_events)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a randomized trace for Exp 1: EP(status_ok & load_lt_100 & !critical_alarm) with shared "
        "communication events."
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
                    f"Trace for Experiment 1 (randomized) successfully written to {args.output}"
                )
            except IOError as e:
                print(f"Error writing to file {args.output}: {e}")
        else:
            print(trace_data)
