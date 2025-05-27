# trace_utils.py
import random
import csv
from typing import List, Dict, Set


def generate_trace_file(
        filename: str,
        num_events_total: int,
        system_processes: List[str],
        prop_map: Dict[int, List[str]],  # Maps event_index -> list of props for that event
        proc_map: Dict[int, str]  # Maps event_index -> assigned process for that event
) -> None:
    """
    Generates a CSV trace file with specified events and properties.

    Args:
        filename: The name of the output CSV file.
        num_events_total: Total number of events to generate in the trace.
        system_processes: A list of process names (e.g., ["P", "Q", "R"]).
        prop_map: A dictionary where keys are 1-based event indices and values are
                  lists of propositions true for that event.
        proc_map: A dictionary where keys are 1-based event indices and values are
                  the process ID string that executes that event.
    """
    trace_events_data = []

    # process_clocks stores the current logical clock value for each process
    process_clocks: Dict[str, int] = {p: 0 for p in system_processes}

    # For each event, its vector clock will be a snapshot of all process_clocks,
    # with the executing process's clock incremented *for that event*.
    # This models that an event carries the timestamp of its occurrence.

    for i in range(1, num_events_total + 1):
        event_id = f"ev{i}"

        # Determine the process for this event
        # If a specific process is assigned for this event index, use it.
        # Otherwise, pick a random process from the system processes.
        assigned_process = proc_map.get(i, random.choice(system_processes))

        if not assigned_process or assigned_process not in system_processes:
            # Fallback if proc_map gives an invalid process or if system_processes is empty
            if not system_processes:  # Should not happen if called correctly
                raise ValueError("system_processes list cannot be empty.")
            assigned_process = random.choice(system_processes)

        # Increment the clock for the process executing this event
        process_clocks[assigned_process] += 1

        # The event's vector clock is the current state of all process clocks
        # (reflecting its own clock just advanced).
        vc_snapshot: Dict[str, int] = process_clocks.copy()

        vc_string_parts = [f"{p}:{v}" for p, v in vc_snapshot.items()]
        vc_csv_string = ";".join(sorted(vc_string_parts))  # Sort for consistent output

        # Determine propositions for this event
        event_props_set: Set[str] = set(prop_map.get(i, []))

        # Optionally add some random "filler" propositions to other events
        if not event_props_set and num_events_total > 5 and random.random() < 0.1:  # Add filler to ~10% of non-key events
            filler_prop = f"filler_{random.choice(['x', 'y', 'z'])}P{random.choice(system_processes)}"
            event_props_set.add(filler_prop)

        props_csv_string = "|".join(sorted(list(event_props_set)))

        trace_events_data.append([event_id, assigned_process, vc_csv_string, props_csv_string])

    # Write to CSV
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        # Write the system_processes directive
        writer.writerow([f"# system_processes: {'|'.join(sorted(system_processes))}"])
        # Write the CSV header
        writer.writerow(["eid", "processes", "vc", "props"])
        # Write the event data
        writer.writerows(trace_events_data)

    print(f"Generated trace with {len(trace_events_data)} events: {filename}")