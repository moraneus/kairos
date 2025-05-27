# convert_csv_to_poet_json.py

import csv
import json
import argparse
from pathlib import Path
from typing import List, Dict, Set, Any, Optional


def parse_vc_string(vc_str: str) -> Dict[str, int]:
    """
    Parses a semicolon-separated VC string (e.g., "P1:1;P2:0") into a dictionary.
    Handles potential leading/trailing spaces around components.
    """
    vc_dict: Dict[str, int] = {}
    if not vc_str:
        return vc_dict
    try:
        pairs = vc_str.split(';')
        for pair in pairs:
            if not pair.strip():  # Skip empty parts if there are ;;
                continue
            proc, clock_val_str = pair.split(':', 1)  # Split only on the first colon
            vc_dict[proc.strip()] = int(clock_val_str.strip())
    except ValueError as e:
        # Catch errors like not enough values to unpack (no ':') or non-integer clock values
        raise ValueError(f"Malformed VC string component in '{vc_str}': {e}")
    return vc_dict


def convert_trace(csv_filepath: Path, json_filepath: Path) -> None:
    """
    Converts a trace file from the custom CSV format to the PoET JSON format.
    Processes in the output PoET JSON will be named P1, P2, P3,...
    based on the order in the '# system_processes:' directive from the CSV.
    """
    raw_events_data: List[Dict[str, str]] = []
    original_ordered_processes: Optional[List[str]] = None

    # --- Step 1: Read CSV and determine original process order ---
    try:
        with open(csv_filepath, 'r', newline='', encoding='utf-8') as csvfile:
            lines = list(csvfile)

            data_lines_start_index = 0
            directive_found = False
            for i, line in enumerate(lines):
                stripped_line = line.strip()
                if stripped_line.startswith("# system_processes:"):
                    if directive_found:
                        raise ValueError("Multiple '# system_processes:' directives found.")
                    directive_content = stripped_line.split(":", 1)[1].strip()
                    original_ordered_processes = [p.strip() for p in directive_content.split("|") if p.strip()]
                    data_lines_start_index = i + 1
                    directive_found = True
                    # Continue to find actual start of CSV data after potential blank lines
                elif directive_found and not stripped_line:
                    data_lines_start_index = i + 1
                elif stripped_line and not stripped_line.startswith("#"):
                    if not directive_found:
                        data_lines_start_index = i
                    break

            if data_lines_start_index >= len(lines) or not lines[data_lines_start_index].strip():
                print(f"Warning: No data rows or header found in {csv_filepath} after line {data_lines_start_index}.")
                num_procs_for_json = len(original_ordered_processes) if original_ordered_processes else 0
                poet_data_empty: Dict[str, Any] = {"processes": num_procs_for_json, "events": []}
                with open(json_filepath, 'w', encoding='utf-8') as jsonfile:
                    json.dump(poet_data_empty, jsonfile, indent=4, sort_keys=True)
                print(f"Generated PoET JSON file (potentially empty or with process count only): {json_filepath}")
                return

            csv_reader = csv.DictReader(lines[data_lines_start_index:])
            if not csv_reader.fieldnames:
                raise ValueError("CSV file is missing a header row or is empty after directive.")

            fieldnames_normalized = [f.strip().lower() for f in csv_reader.fieldnames]

            id_field_internal = None
            if "eid" in fieldnames_normalized:
                id_field_internal = "eid"
            elif "id" in fieldnames_normalized:
                id_field_internal = "id"
            else:
                raise ValueError("CSV header must contain 'eid' or 'id'.")

            required_headers_normalized = {id_field_internal, "processes", "vc", "props"}
            if not required_headers_normalized.issubset(set(fieldnames_normalized)):
                missing = required_headers_normalized - set(fieldnames_normalized)
                raise ValueError(f"CSV header missing required columns: {missing}")

            for row in csv_reader:
                # Normalize keys from the row for consistent access
                normalized_row = {k.strip().lower(): v.strip() if v else "" for k, v in row.items()}
                raw_events_data.append(normalized_row)

                # If no directive, attempt to discover all processes to establish an order later
                if original_ordered_processes is None:
                    # This part is now less critical if we mandate the directive for canonical names,
                    # but can be kept as a fallback for discovery if needed elsewhere.
                    # For Px renaming, the directive is the source of truth for order.
                    pass

    except FileNotFoundError:
        print(f"Error: Input CSV file not found at {csv_filepath}");
        return
    except Exception as e:
        print(f"Error reading or parsing CSV file {csv_filepath}: {e}");
        return

    if not original_ordered_processes:
        # If still no original_ordered_processes (directive was missing)
        # we must infer them to create the Px mapping. This is a fallback.
        # This fallback will create a sorted list of unique process names found in the trace.
        # It's better if the directive is present for a canonical ordering.
        all_procs_found_in_data: Set[str] = set()
        for r_event_data in raw_events_data:  # Use r_event_data to avoid conflict
            procs_in_event_str = r_event_data.get("processes", "")
            all_procs_found_in_data.update(p.strip() for p in procs_in_event_str.split("|") if p.strip())
            vc_dict_temp = parse_vc_string(r_event_data.get("vc", ""))
            all_procs_found_in_data.update(vc_dict_temp.keys())

        if all_procs_found_in_data:
            original_ordered_processes = sorted(list(all_procs_found_in_data))
            print(
                f"Warning: '# system_processes' directive not found. Inferred and sorted process order for Px mapping: {original_ordered_processes}")
        else:
            original_ordered_processes = []
            print("Warning: No system processes defined by directive or found in trace events for Px mapping.")

    # --- Step 2: Create mapping from original process names to Px names ---
    # Px names will be P1, P2, ... based on the order in original_ordered_processes
    process_to_px_map: Dict[str, str] = {
        original_name: f"P{i + 1}"
        for i, original_name in enumerate(original_ordered_processes)
    }
    # Canonical Px names, ordered, for use in the PoET JSON output
    canonical_px_process_names: List[str] = [
        process_to_px_map[og_name] for og_name in original_ordered_processes
    ]

    poet_events_list: List[List[Any]] = []  # Renamed to avoid conflict
    id_field_to_use_internal = "eid" if "eid" in raw_events_data[0] else "id" if raw_events_data else None

    for csv_event_data in raw_events_data:  # Use csv_event_data to avoid conflict
        if id_field_to_use_internal is None:  # Should not happen if header was validated
            print(f"Warning: Skipping row due to undetermined ID field: {csv_event_data}")
            continue

        poet_event_id_val = csv_event_data.get(id_field_to_use_internal, f"unknown_ev_{len(poet_events_list)}")

        original_procs_str = csv_event_data.get("processes", "")
        # Map original process names to Px names for the "processes" list in PoET format
        poet_event_processes = sorted([
            process_to_px_map[p.strip()]
            for p in original_procs_str.split("|") if p.strip() and p.strip() in process_to_px_map
        ])

        props_str_val = csv_event_data.get("props", "")  # Renamed
        poet_event_propositions = sorted([p.strip() for p in props_str_val.split("|") if p.strip()])
        if not props_str_val.strip() and not poet_event_propositions: poet_event_propositions = []

        vc_str_val = csv_event_data.get("vc", "")  # Renamed
        original_vc_dict = parse_vc_string(vc_str_val)

        poet_vc_array_vals: List[int] = []  # Renamed
        # Build the VC array based on the canonical Px order
        for original_proc_name in original_ordered_processes:  # Iterate in the defined order
            canonical_px_name = process_to_px_map[original_proc_name]
            # Get the clock value for the *original* process name from the CSV's VC dict
            clock_value = original_vc_dict.get(original_proc_name, 0)
            poet_vc_array_vals.append(clock_value)

        poet_events_list.append([
            poet_event_id_val,
            poet_event_processes,  # List of Px names
            poet_event_propositions,
            poet_vc_array_vals  # Ordered list of integers
        ])

    num_procs_for_json_output = len(canonical_px_process_names)  # Renamed

    poet_output_data_structure: Dict[str, Any] = {  # Renamed
        "processes": num_procs_for_json_output,
        "events": poet_events_list
    }

    try:
        with open(json_filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(poet_output_data_structure, jsonfile, indent=4, sort_keys=True)
        print(f"Successfully converted '{csv_filepath}' to PoET JSON format at '{json_filepath}'")
        print(f"Total processes in JSON (as Px): {num_procs_for_json_output}")
        if original_ordered_processes:
            print(f"Original process order mapped to Px: {original_ordered_processes} -> {canonical_px_process_names}")
    except Exception as e:
        print(f"Error writing JSON file {json_filepath}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert custom CSV trace to PoET JSON format with Px process renaming.")
    parser.add_argument("csv_input", type=Path, help="Path to the input CSV trace file.")
    parser.add_argument("json_output", type=Path, help="Path for the output PoET JSON trace file.")

    args = parser.parse_args()

    convert_trace(args.csv_input, args.json_output)