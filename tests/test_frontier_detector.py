# tests/test_frontier_detector.py
# Test the frontier detector implementation against examples from the paper
#
# This test file demonstrates that the frontier detector works exactly
# as described in Section 4 and Appendix C (Example 1) of the paper.

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.event import Event, VectorClock
from core.frontier_detector import FrontierDetector


def test_example_from_paper():
    """
    Test Example 1 from Appendix C of the paper.

    The example uses the partial order execution from Figure 1 with:
    - Three processes: p1, p2, p3
    - Events: {ι, α1, α2, α3, β1, β2, β3}
    - Minterms: γ1 = t2, γ2 = r1, γ3 = q1q2

    The algorithm should find the minimum frontier M = [α3, β2, β3] satisfying η.
    """

    # Define processes
    processes = {"p1", "p2", "p3"}

    # Define minterms as described in the paper
    # γ1 = t2 (for p1), γ2 = r1 (for p2), γ3 = q1q2 (for p3)
    minterms = {
        "p1": ["t2"],  # p1 needs t2
        "p2": ["r1"],  # p2 needs r1
        "p3": ["q1", "q2"],  # p3 needs both q1 and q2
    }

    # Create frontier detector
    detector = FrontierDetector(minterms=minterms, all_processes=processes)

    print("\nMinterms:")
    print(f"  γ1 (p1) = t2")
    print(f"  γ2 (p2) = r1")
    print(f"  γ3 (p3) = q1 ∧ q2")

    # Create events following the linearization σ = ι, α1, β1, α2, β2, α3, β3

    # ι: initial event
    iota = Event(
        eid="ι",
        processes=frozenset({"p1", "p2", "p3"}),
        vc=VectorClock({"p1": 0, "p2": 0, "p3": 0}),
        props=frozenset(["!t1", "!t2", "r1", "r2", "q1", "!q2"]),  # L(ι)
    )

    # α1: event on p1
    alpha1 = Event(
        eid="α1",
        processes=frozenset({"p1"}),
        vc=VectorClock({"p1": 1, "p2": 0, "p3": 0}),
        props=frozenset(["!t1", "t2"]),  # L(α1, p1) = t1̄t2
    )

    # β1: event on p3
    beta1 = Event(
        eid="β1",
        processes=frozenset({"p3"}),
        vc=VectorClock({"p1": 0, "p2": 0, "p3": 1}),
        props=frozenset(["q1", "!q2"]),  # L(β1, p3) = q1q2̄
    )

    # α2: shared event between p1 and p2
    alpha2 = Event(
        eid="α2",
        processes=frozenset({"p1", "p2"}),
        vc=VectorClock({"p1": 2, "p2": 1, "p3": 0}),
        props=frozenset(["t1", "!t2", "r1", "!r2"]),  # L(α2)
    )

    # β2: shared event between p2 and p3
    beta2 = Event(
        eid="β2",
        processes=frozenset({"p2", "p3"}),
        vc=VectorClock({"p1": 2, "p2": 2, "p3": 2}),
        props=frozenset(["r1", "r2", "q1", "!q2"]),  # L(β2)
    )

    # α3: event on p1
    alpha3 = Event(
        eid="α3",
        processes=frozenset({"p1"}),
        vc=VectorClock({"p1": 3, "p2": 1, "p3": 0}),
        props=frozenset(["t1", "t2"]),  # L(α3, p1) = t1t2
    )

    # β3: event on p3
    beta3 = Event(
        eid="β3",
        processes=frozenset({"p3"}),
        vc=VectorClock({"p1": 2, "p2": 2, "p3": 3}),
        props=frozenset(["q1", "q2"]),  # L(β3, p3) = q1q2
    )

    # Process events in the linearization order
    events = [iota, alpha1, beta1, alpha2, beta2, alpha3, beta3]

    print("\nProcessing events in order: ι → α1 → β1 → α2 → β2 → α3 → β3")
    print("-" * 60)

    result_frontier = None
    for i, event in enumerate(events):
        print(f"\nStep {i+1}: Processing event {event.eid}")
        print(f"  Processes: {sorted(event.processes)}")
        print(f"  Vector clock: {event.vc}")
        print(f"  Props: {sorted(event.props)}")

        # Process event with frontier detector
        detected = detector.process_new_event(event)

        # Show current M vector state
        m_vector = detector.get_current_M()
        print(f"  Current M vector:")
        for proc in sorted(processes):
            e = m_vector.get(proc)
            if e:
                print(f"    M[{proc}] = {e.eid}")
            else:
                print(f"    M[{proc}] = None")

        if detected:
            result_frontier = detected
            print(f"\n  ✓ FRONTIER DETECTED: {detected}")
            print(f"    This is the minimum frontier satisfying η = γ1 ∧ γ2 ∧ γ3")
            break

    print("\n" + "=" * 80)
    print("RESULTS:")
    print("=" * 80)

    if result_frontier:
        print(f"\n✓ Successfully detected minimum frontier: {result_frontier}")

        # Verify it matches the expected result from the paper
        expected_events = {"α3": "p1", "β2": "p2", "β3": "p3"}
        actual_events = {}
        for proc, event in result_frontier.events_dict.items():
            actual_events[event.eid] = proc

        # Check if the frontier contains the expected events
        is_correct = True
        for eid, proc in expected_events.items():
            if eid not in actual_events:
                print(f"  ✗ Missing expected event: {eid} for process {proc}")
                is_correct = False
            elif actual_events[eid] != proc:
                print(
                    f"  ✗ Event {eid} is for wrong process: expected {proc}, got {actual_events[eid]}"
                )
                is_correct = False

        if is_correct and len(actual_events) == len(expected_events):
            print("\n  ✓ Result matches the paper's Example 1 exactly!")
            print("    Expected: M = [α3, β2, β3]")
            print(f"    Got: M = [{', '.join(sorted(actual_events.keys()))}]")
        else:
            print("\n  ✗ Result does not match the paper's example")
            assert (
                False
            ), f"Result does not match expected frontier: got {actual_events}, expected {expected_events}"

    else:
        print("\n✗ No frontier detected (algorithm should have found M = [α3, β2, β3])")
        assert (
            False
        ), "No frontier detected, but algorithm should have found M = [α3, β2, β3]"

    # Assert the test passed
    assert result_frontier is not None, "Frontier should have been detected"
    assert is_correct, "Detected frontier should match the paper's expected result"


def test_component_and_frontier_correction():
    """
    Test that component correction and frontier correction work as described.
    """

    processes = {"p1", "p2"}
    minterms = {"p1": ["a"], "p2": ["b"]}

    detector = FrontierDetector(minterms=minterms, all_processes=processes)

    # Create a sequence of events that requires corrections
    e1 = Event(
        eid="e1",
        processes=frozenset({"p1"}),
        vc=VectorClock({"p1": 1, "p2": 0}),
        props=frozenset(["a"]),  # Satisfies γ1
    )

    e2 = Event(
        eid="e2",
        processes=frozenset({"p2"}),
        vc=VectorClock({"p1": 0, "p2": 1}),
        props=frozenset(["c"]),  # Does not satisfy γ2
    )

    e3 = Event(
        eid="e3",
        processes=frozenset({"p1", "p2"}),  # Shared event
        vc=VectorClock({"p1": 2, "p2": 2}),
        props=frozenset(["a", "b"]),  # Satisfies both γ1 and γ2
    )

    print("\nProcessing events to test correction mechanisms:")

    # Process e1
    print("\n1. Processing e1 (p1, satisfies γ1):")
    detector.process_new_event(e1)
    m = detector.get_current_M()
    print(f"   M[p1] = {m['p1'].eid if m.get('p1') else 'None'}")
    print(f"   M[p2] = {m['p2'].eid if m.get('p2') else 'None'}")

    # Process e2
    print("\n2. Processing e2 (p2, does NOT satisfy γ2):")
    detector.process_new_event(e2)
    m = detector.get_current_M()
    print(f"   M[p1] = {m['p1'].eid if m.get('p1') else 'None'}")
    print(f"   M[p2] = {m['p2'].eid if m.get('p2') else 'None'}")

    # Process e3 - should trigger corrections
    print("\n3. Processing e3 (shared, satisfies both γ1 and γ2):")
    result = detector.process_new_event(e3)
    m = detector.get_current_M()
    print(f"   M[p1] = {m['p1'].eid if m.get('p1') else 'None'}")
    print(f"   M[p2] = {m['p2'].eid if m.get('p2') else 'None'}")

    if result:
        print(f"\n✓ Frontier detected after corrections: {result}")
        print("  Component correction updated M[p2] to e3 (satisfies γ2)")
        print("  Frontier correction ensured consistency")
    else:
        print("\n✗ No frontier detected (corrections may have failed)")
        assert False, "Frontier should have been detected after corrections"

    # Assert the test passed
    assert result is not None, "Frontier should have been detected"

    # Verify the frontier contains the expected event
    assert "e3" in str(result), "Frontier should contain the corrected event e3"


# This module can be run with pytest to test the frontier detector implementation
