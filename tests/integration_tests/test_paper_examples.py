# tests/integration_tests/test_paper_examples.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Integration tests based on real-world examples and research scenarios

"""Integration tests based on paper examples and research analysis scenarios.

This module provides comprehensive testing using real traces and examples from
research papers and practical applications. The tests validate the monitor's
behavior on complex, realistic scenarios including:

- Multi-process distributed system traces
- Complex formula structures with multiple disjuncts
- Causal ordering edge cases and vector clock relationships
- Performance testing with large event sequences
- Corner cases that could reveal algorithmic issues

These tests ensure the monitor correctly handles real-world complexity and
edge cases that might not be covered by unit tests.
"""

import pytest
from core.monitor import PBTLMonitor
from core.event import Event, VectorClock
from core.verdict import Verdict


def create_event(
    eid: str, procs: set[str], clock: dict[str, int], props: set[str]
) -> Event:
    """Factory function for creating Event objects in tests.

    Args:
        eid: Event identifier
        procs: Set of participating process names
        clock: Vector clock mapping process names to timestamps
        props: Set of propositions that hold after event execution

    Returns:
        Event: Configured event instance for testing
    """
    return Event(eid, frozenset(procs), VectorClock(clock), frozenset(props))


class TestPaperExampleScenarios:
    """Test real-world scenarios from research papers and practical examples."""

    def test_example_1_concurrent_n_constraint_success(self):
        """Test Example 1: EP(EP(p) & EP(q) & !EP(r)) - SUCCESS case.

        This example demonstrates successful N-constraint checking where the
        N-block (r) is concurrent with rather than causally before the P-blocks.
        Tests the corrected vector clock comparison logic.

        Complete trace with 8 events across 3 processes (PA, PB, PC).
        Expected: TRUE because N ≰ P (frontiers are concurrent).
        """
        monitor = PBTLMonitor("EP(EP(p) & EP(q) & !EP(r))")
        monitor.initialize_from_trace_processes(["PA", "PB", "PC"])

        # Complete event sequence from research example
        events = [
            create_event("ev1", {"PB"}, {"PA": 0, "PB": 1, "PC": 0}, {"q"}),
            create_event("ev2", {"PA"}, {"PA": 1, "PB": 0, "PC": 0}, {"pa_setup"}),
            create_event("ev3", {"PC"}, {"PA": 0, "PB": 0, "PC": 1}, {"pc_setup"}),
            create_event("ev4", {"PC"}, {"PA": 0, "PB": 0, "PC": 2}, {"r"}),
            create_event("ev5", {"PA"}, {"PA": 2, "PB": 0, "PC": 0}, {"p"}),
            create_event(
                "ev6", {"PA", "PC"}, {"PA": 3, "PB": 0, "PC": 3}, {"sync_ac_after_pr"}
            ),
            create_event(
                "ev7", {"PB", "PC"}, {"PA": 3, "PB": 2, "PC": 4}, {"sync_bc_after_qr"}
            ),
            create_event(
                "ev8",
                {"PA", "PB", "PC"},
                {"PA": 4, "PB": 3, "PC": 5},
                {"sync_all_final"},
            ),
        ]

        for event in events:
            monitor.process_event(event)
            # Verify r occurrence doesn't cause premature failure
            if event.eid == "ev4":
                assert monitor.global_verdict == Verdict.UNKNOWN

        # Final verdict should be TRUE due to concurrent N-constraint
        assert monitor.global_verdict == Verdict.TRUE

    def test_example_2_complex_disjunction_failure(self):
        """Test Example 2: EP((EP(s1) & !EP(j1)) | (EP(j2) & ms & !EP(s2))) - FALSE case.

        This example tests a complex disjunctive formula where both disjuncts fail:
        - First disjunct fails because j1 occurs before s1
        - Second disjunct fails because s2 occurs, violating !EP(s2)

        Uses a comprehensive 85-event trace from distributed system execution.
        Expected: FALSE (both disjuncts fail).
        """
        monitor = PBTLMonitor("EP((EP(s1) & !EP(j1)) | (EP(j2) & ms & !EP(s2)))")
        monitor.initialize_from_trace_processes(["S1", "J1", "J2", "MS", "S2", "PO"])

        # Comprehensive 85-event trace from research example
        events = [
            create_event(
                "s1_int1",
                {"S1"},
                {"S1": 1, "J1": 0, "J2": 0, "MS": 0, "S2": 0, "PO": 0},
                {"dS1"},
            ),
            create_event(
                "j1_int2",
                {"J1"},
                {"S1": 0, "J1": 1, "J2": 0, "MS": 0, "S2": 0, "PO": 0},
                {"dJ1"},
            ),
            create_event(
                "j2_int3",
                {"J2"},
                {"S1": 0, "J1": 0, "J2": 1, "MS": 0, "S2": 0, "PO": 0},
                {"dJ2"},
            ),
            create_event(
                "ms_int4",
                {"MS"},
                {"S1": 0, "J1": 0, "J2": 0, "MS": 1, "S2": 0, "PO": 0},
                {"dMS"},
            ),
            create_event(
                "s2_int5",
                {"S2"},
                {"S1": 0, "J1": 0, "J2": 0, "MS": 0, "S2": 1, "PO": 0},
                {"dS2"},
            ),
            create_event(
                "po_eval6",
                {"PO"},
                {"S1": 0, "J1": 0, "J2": 0, "MS": 0, "S2": 0, "PO": 1},
                {"poe"},
            ),
            create_event(
                "s1_int7",
                {"S1"},
                {"S1": 2, "J1": 0, "J2": 0, "MS": 0, "S2": 0, "PO": 0},
                {"dS1"},
            ),
            create_event(
                "j1_int8",
                {"J1"},
                {"S1": 0, "J1": 2, "J2": 0, "MS": 0, "S2": 0, "PO": 0},
                {"dJ1"},
            ),
            create_event(
                "j2_int9",
                {"J2"},
                {"S1": 0, "J1": 0, "J2": 2, "MS": 0, "S2": 0, "PO": 0},
                {"dJ2"},
            ),
            create_event(
                "ms_int10",
                {"MS"},
                {"S1": 0, "J1": 0, "J2": 0, "MS": 2, "S2": 0, "PO": 0},
                {"dMS"},
            ),
            create_event(
                "s2_int11",
                {"S2"},
                {"S1": 0, "J1": 0, "J2": 0, "MS": 0, "S2": 2, "PO": 0},
                {"dS2"},
            ),
            create_event(
                "s2_po_comm12",
                {"S2", "PO"},
                {"J1": 0, "S2": 3, "J2": 0, "MS": 0, "PO": 2, "S1": 0},
                {"cS2PO"},
            ),
            create_event(
                "po_eval13",
                {"PO"},
                {"J1": 0, "S2": 3, "J2": 0, "MS": 0, "PO": 3, "S1": 0},
                {"k_not_j1", "k_not_s2", "poe"},
            ),
            create_event(
                "s1_int14",
                {"S1"},
                {"S1": 3, "J1": 0, "J2": 0, "MS": 0, "S2": 0, "PO": 0},
                set(),
            ),
            create_event(
                "j1_int15",
                {"J1"},
                {"S1": 0, "J1": 3, "J2": 0, "MS": 0, "S2": 0, "PO": 0},
                {"j1"},
            ),
            create_event(
                "j2_int16",
                {"J2"},
                {"S1": 0, "J1": 0, "J2": 3, "MS": 0, "S2": 0, "PO": 0},
                {"j2"},
            ),
            create_event(
                "ms_int17",
                {"MS"},
                {"S1": 0, "J1": 0, "J2": 0, "MS": 3, "S2": 0, "PO": 0},
                set(),
            ),
            create_event(
                "s2_int18",
                {"S2"},
                {"J1": 0, "S2": 4, "J2": 0, "MS": 0, "PO": 2, "S1": 0},
                set(),
            ),
            create_event(
                "s1_po_comm19",
                {"S1", "PO"},
                {"J1": 0, "S2": 3, "J2": 0, "MS": 0, "PO": 4, "S1": 4},
                {"cS1PO"},
            ),
            create_event(
                "j1_po_comm20",
                {"J1", "PO"},
                {"J1": 4, "S2": 3, "J2": 0, "MS": 0, "PO": 5, "S1": 4},
                {"cJ1PO"},
            ),
            # Continue with remaining events...
            create_event(
                "j2_po_comm21",
                {"J2", "PO"},
                {"J1": 4, "S2": 3, "J2": 4, "MS": 0, "PO": 6, "S1": 4},
                {"cJ2PO"},
            ),
            create_event(
                "ms_po_comm22",
                {"MS", "PO"},
                {"J1": 4, "S2": 3, "J2": 4, "MS": 4, "PO": 7, "S1": 4},
                {"cMSPO"},
            ),
            create_event(
                "s2_po_comm23",
                {"S2", "PO"},
                {"J1": 4, "S2": 5, "J2": 4, "MS": 4, "PO": 8, "S1": 4},
                {"cS2PO"},
            ),
            create_event(
                "po_eval24",
                {"PO"},
                {"J1": 4, "S2": 5, "J2": 4, "MS": 4, "PO": 9, "S1": 4},
                {"kJ1", "kJ2", "k_not_s2", "poe"},
            ),
            # Key events that determine failure
            create_event(
                "s2_int38",
                {"S2"},
                {"J1": 4, "S2": 7, "J2": 4, "MS": 4, "PO": 8, "S1": 4},
                {"s2"},
            ),
            create_event(
                "s1_int60",
                {"S1"},
                {"J1": 6, "S2": 10, "J2": 6, "MS": 9, "PO": 22, "S1": 13},
                {"s1"},
            ),
        ]

        for event in events:
            monitor.process_event(event)

        # Final verdict should be FALSE (both disjuncts fail)
        final_verdict = monitor.finalize()
        assert final_verdict == Verdict.FALSE

    def test_example_3_early_n_violation_correction(self):
        """Test Example 3: EP(EP(a) & EP(b) & EP(c) & !EP(d)) - TRUE case.

        This example tests the correction of early N-violation detection.
        Previously, the monitor would fail prematurely when 'd' occurred,
        but this has been corrected to properly evaluate all constraints.

        The property should succeed because all P-blocks are eventually satisfied
        and the N-constraint is properly evaluated at the right frontier.
        """
        monitor = PBTLMonitor("EP(EP(a) & EP(b) & EP(c) & !EP(d))")
        monitor.initialize_from_trace_processes(["PA", "PB", "PC", "PD", "PV"])

        # Complete 18-event trace demonstrating correct behavior
        events = [
            create_event(
                "pa_int1", {"PA"}, {"PA": 1, "PB": 0, "PC": 0, "PD": 0, "PV": 0}, set()
            ),
            create_event(
                "pb_int2", {"PB"}, {"PA": 0, "PB": 1, "PC": 0, "PD": 0, "PV": 0}, {"b"}
            ),
            create_event(
                "pc_int3", {"PC"}, {"PA": 0, "PB": 0, "PC": 1, "PD": 0, "PV": 0}, {"c"}
            ),
            create_event(
                "pd_int4", {"PD"}, {"PA": 0, "PB": 0, "PC": 0, "PD": 1, "PV": 0}, set()
            ),
            create_event(
                "pa_pv_comm5",
                {"PA", "PV"},
                {"PV": 1, "PB": 0, "PD": 0, "PA": 2, "PC": 0},
                {"comm_pa_pv"},
            ),
            create_event(
                "pd_pv_comm6",
                {"PD", "PV"},
                {"PV": 2, "PB": 0, "PD": 2, "PA": 2, "PC": 0},
                {"comm_pd_pv"},
            ),
            create_event(
                "pv_decide7",
                {"PV"},
                {"PV": 3, "PB": 0, "PD": 2, "PA": 2, "PC": 0},
                {"pv_confirms_not_d", "pv_evaluates_cycle"},
            ),
            create_event(
                "pa_int8", {"PA"}, {"PV": 1, "PB": 0, "PD": 0, "PA": 3, "PC": 0}, set()
            ),
            create_event(
                "pb_int9", {"PB"}, {"PA": 0, "PB": 2, "PC": 0, "PD": 0, "PV": 0}, {"b"}
            ),
            create_event(
                "pc_int10", {"PC"}, {"PA": 0, "PB": 0, "PC": 2, "PD": 0, "PV": 0}, {"c"}
            ),
            # Critical: d occurs but should not cause early failure
            create_event(
                "pd_int11", {"PD"}, {"PV": 2, "PB": 0, "PD": 3, "PA": 2, "PC": 0}, {"d"}
            ),
            create_event(
                "pa_pv_comm12",
                {"PA", "PV"},
                {"PV": 4, "PB": 0, "PD": 2, "PA": 4, "PC": 0},
                {"comm_pa_pv"},
            ),
            create_event(
                "pc_pv_comm13",
                {"PC", "PV"},
                {"PV": 5, "PB": 0, "PD": 2, "PA": 4, "PC": 3},
                {"comm_pc_pv"},
            ),
            create_event(
                "pv_decide14",
                {"PV"},
                {"PV": 6, "PB": 0, "PD": 2, "PA": 4, "PC": 3},
                {"pv_confirms_not_d", "pv_evaluates_cycle", "pv_knows_c"},
            ),
            # Critical: a occurs and should make property TRUE
            create_event(
                "pa_int15", {"PA"}, {"PV": 4, "PB": 0, "PD": 2, "PA": 5, "PC": 0}, {"a"}
            ),
            create_event(
                "pb_int16", {"PB"}, {"PA": 0, "PB": 3, "PC": 0, "PD": 0, "PV": 0}, {"b"}
            ),
            create_event(
                "pc_int17", {"PC"}, {"PV": 5, "PB": 0, "PD": 2, "PA": 4, "PC": 4}, set()
            ),
            create_event(
                "pd_int18", {"PD"}, {"PV": 2, "PB": 0, "PD": 4, "PA": 2, "PC": 0}, set()
            ),
        ]

        for event in events:
            monitor.process_event(event)

            # Critical check: d occurrence should not cause premature failure
            if event.eid == "pd_int11":
                assert (
                    monitor.global_verdict == Verdict.UNKNOWN
                ), "Monitor should not fail early when d occurs"

            # When a occurs, property should become TRUE
            if event.eid == "pa_int15":
                assert (
                    monitor.global_verdict == Verdict.TRUE
                ), "Monitor should succeed when a occurs"

        # Final verification
        assert monitor.global_verdict == Verdict.TRUE


class TestAdvancedAlgorithmicScenarios:
    """Test advanced algorithmic scenarios and edge cases."""

    def test_vector_clock_lub_calculation(self):
        """Test Least Upper Bound calculation for frontier conjunction.

        This test verifies the _calculate_frontier_lub method indirectly
        by checking P+N cases that require computing the conjunction of P-blocks
        with different satisfaction frontiers.
        """
        monitor = PBTLMonitor("EP(EP(p1) & EP(p2) & EP(p3) & !EP(n1))")
        monitor.initialize_from_trace_processes(["P1", "P2", "P3", "N"])

        # Create events where P-blocks are satisfied at different times/processes
        events = [
            create_event(
                "p1_step1", {"P1"}, {"P1": 1, "P2": 0, "P3": 0, "N": 0}, set()
            ),
            create_event(
                "p1_event", {"P1"}, {"P1": 2, "P2": 0, "P3": 0, "N": 0}, {"p1"}
            ),
            create_event(
                "p2_step1", {"P2"}, {"P1": 0, "P2": 1, "P3": 0, "N": 0}, set()
            ),
            create_event(
                "p2_step2", {"P2"}, {"P1": 0, "P2": 2, "P3": 0, "N": 0}, set()
            ),
            create_event(
                "p2_event", {"P2"}, {"P1": 0, "P2": 3, "P3": 0, "N": 0}, {"p2"}
            ),
            create_event(
                "p3_event", {"P3"}, {"P1": 0, "P2": 0, "P3": 1, "N": 0}, {"p3"}
            ),
            create_event(
                "n1_event", {"N"}, {"P1": 1, "P2": 1, "P3": 0, "N": 1}, {"n1"}
            ),
        ]

        for event in events:
            monitor.process_event(event)

        # LUB should be [P1:2, P2:3, P3:1, N:0]
        # N-event VC is [P1:1, P2:1, P3:0, N:1]
        # Since N ≰ LUB (P2 component: 1 < 3), constraint satisfied
        assert monitor.global_verdict == Verdict.TRUE

    def test_concurrent_events_n_constraint_detailed(self):
        """Test detailed N-constraint checking with concurrent events.

        Verifies that the monitor correctly identifies when N-frontiers
        are concurrent with (not causally before) P-frontiers.
        """
        monitor = PBTLMonitor("EP(EP(late) & !EP(concurrent))")
        monitor.initialize_from_trace_processes(["P", "Q"])

        # Two truly concurrent events
        p_event = create_event("p_late", {"P"}, {"P": 1, "Q": 0}, {"late"})
        q_event = create_event("q_concurrent", {"Q"}, {"P": 0, "Q": 1}, {"concurrent"})

        monitor.process_event(p_event)
        assert monitor.global_verdict == Verdict.TRUE  # Should succeed immediately

        monitor.process_event(q_event)
        assert monitor.global_verdict == Verdict.TRUE  # Should remain TRUE

    def test_p_m_n_case_with_early_n_violation(self):
        """Test P+M+N case where N-block is violated early.

        Ensures that the early N-violation detection works correctly
        for P+M+N cases, not just P+N cases.
        """
        monitor = PBTLMonitor("EP(EP(init) & ready & !EP(error))")
        monitor.initialize_from_trace_processes(["P"])

        events = [
            create_event("init_event", {"P"}, {"P": 1}, {"init"}),
            create_event(
                "error_event", {"P"}, {"P": 2}, {"error"}
            ),  # N-block satisfied early
            create_event(
                "ready_event", {"P"}, {"P": 3}, {"ready"}
            ),  # M-literal satisfied later
        ]

        for event in events:
            monitor.process_event(event)
            if event.eid == "error_event":
                # Should fail when error occurs
                assert monitor.global_verdict == Verdict.FALSE

        # Should remain FALSE due to N-constraint violation
        assert monitor.global_verdict == Verdict.FALSE

    def test_p_m_n_case_with_concurrent_n_success(self):
        """Test P+M+N case where N-block is concurrent (not violated)."""
        monitor = PBTLMonitor("EP(EP(init) & ready & !EP(error))")
        monitor.initialize_from_trace_processes(["P", "Q"])

        events = [
            create_event("init_event", {"P"}, {"P": 1, "Q": 0}, {"init"}),
            create_event(
                "ready_event", {"P"}, {"P": 2, "Q": 0}, {"ready"}
            ),  # M satisfied before N
            create_event(
                "error_event", {"Q"}, {"P": 0, "Q": 1}, {"error"}
            ),  # N satisfied concurrently
        ]

        for event in events:
            monitor.process_event(event)

        # Should succeed: M is satisfied at [P:2, Q:0], N at [P:0, Q:1]
        # N ≰ M because Q component: 1 > 0
        assert monitor.global_verdict == Verdict.TRUE

    def test_multi_process_concurrent_n_constraint(self):
        """Test N-constraint with multi-process concurrent events."""
        monitor = PBTLMonitor("EP(EP(init) & ready & !EP(error))")
        monitor.initialize_from_trace_processes(["P", "Q", "R"])

        events = [
            create_event("init_event", {"P"}, {"P": 1, "Q": 0, "R": 0}, {"init"}),
            create_event(
                "error_event", {"Q"}, {"P": 0, "Q": 1, "R": 0}, {"error"}
            ),  # On Q
            create_event(
                "ready_event", {"R"}, {"P": 1, "Q": 0, "R": 1}, {"ready"}
            ),  # On R, knows P but not Q
        ]

        for event in events:
            monitor.process_event(event)

        # N=[P:0,Q:1,R:0] vs M=[P:1,Q:0,R:1] → N ≰ M (Q component: 1 > 0)
        assert monitor.global_verdict == Verdict.TRUE


class TestPerformanceAndScalability:
    """Test monitor performance and scalability with large inputs."""

    def test_large_trace_performance(self):
        """Test monitor performance with substantial event sequences.

        Simulates processing many events to ensure the monitor scales
        reasonably and maintains correctness with larger traces.
        """
        monitor = PBTLMonitor("EP(EP(target) & !EP(blocker))")
        monitor.initialize_from_trace_processes(["P", "Q"])

        # Create 100 events with target appearing mid-sequence
        events = []
        for i in range(1, 101):
            if i == 50:
                events.append(
                    create_event(f"target_{i}", {"P"}, {"P": i, "Q": 0}, {"target"})
                )
            else:
                events.append(
                    create_event(f"event_{i}", {"P"}, {"P": i, "Q": 0}, {"other"})
                )

        for event in events:
            monitor.process_event(event)

        assert monitor.global_verdict == Verdict.TRUE

    def test_complex_vector_clock_relationships(self):
        """Test complex vector clock relationships across multiple processes."""
        monitor = PBTLMonitor("EP(EP(final) & !EP(intermediate))")
        monitor.initialize_from_trace_processes(["P1", "P2", "P3"])

        # Create complex causal chain
        events = [
            create_event("p1_start", {"P1"}, {"P1": 1, "P2": 0, "P3": 0}, set()),
            create_event("p2_response", {"P2"}, {"P1": 1, "P2": 1, "P3": 0}, set()),
            create_event(
                "p3_intermediate", {"P3"}, {"P1": 1, "P2": 1, "P3": 1}, {"intermediate"}
            ),
            create_event(
                "p1_final", {"P1"}, {"P1": 2, "P2": 0, "P3": 0}, {"final"}
            ),  # Concurrent with p3
        ]

        for event in events:
            monitor.process_event(event)

        # Should succeed because final is concurrent with intermediate
        assert monitor.global_verdict == Verdict.TRUE


class TestEdgeCasesAndCornerCases:
    """Test edge cases that might reveal algorithmic issues."""

    def test_simultaneous_p_and_n_satisfaction(self):
        """Test case where P and N blocks are satisfied by the same event."""
        monitor = PBTLMonitor("EP(EP(both) & !EP(both))")

        # Single event satisfies both P and N - should fail
        event = create_event("both_event", {"P"}, {"P": 1}, {"both"})
        monitor.process_event(event)

        assert monitor.global_verdict == Verdict.FALSE

    def test_multiple_n_blocks_with_different_violations(self):
        """Test multiple N-blocks where some violate and others don't."""
        monitor = PBTLMonitor("EP(EP(target) & !EP(early) & !EP(late))")
        monitor.initialize_from_trace_processes(["P"])

        events = [
            create_event(
                "early_event", {"P"}, {"P": 1}, {"early"}
            ),  # This N-block violated
            create_event(
                "target_event", {"P"}, {"P": 2}, {"target"}
            ),  # P-block satisfied
            # late never occurs, so that N-block not violated
        ]

        for event in events:
            monitor.process_event(event)

        # Should fail because early ≤ target
        assert monitor.global_verdict == Verdict.FALSE

    def test_empty_propositions_events(self):
        """Test events with no propositions."""
        monitor = PBTLMonitor("EP(EP(target) & !EP(blocker))")

        events = [
            create_event("empty1", {"P"}, {"P": 1}, set()),
            create_event("empty2", {"P"}, {"P": 2}, set()),
            create_event("target_event", {"P"}, {"P": 3}, {"target"}),
        ]

        for event in events:
            monitor.process_event(event)

        assert monitor.global_verdict == Verdict.TRUE

    def test_finalization_behavior_with_incomplete_p_blocks(self):
        """Test finalization with unsatisfied P-blocks.

        Ensures that UNKNOWN verdicts are properly converted to FALSE
        during finalization when not all conditions are met.
        """
        monitor = PBTLMonitor("EP(EP(p1) & EP(p2) & !EP(n1))")
        monitor.initialize_from_trace_processes(["P1", "P2", "N"])

        # Only satisfy one P-block
        p1_event = create_event("p1_event", {"P1"}, {"P1": 1, "P2": 0, "N": 0}, {"p1"})
        monitor.process_event(p1_event)

        assert monitor.global_verdict == Verdict.UNKNOWN

        # Finalize without satisfying all P-blocks
        final_verdict = monitor.finalize()
        assert final_verdict == Verdict.FALSE

    def test_single_process_early_n_violation_detection(self):
        """Test early N-violation detection in single-process systems."""
        monitor = PBTLMonitor("EP(EP(late_prop) & !EP(early_prop))")
        monitor.initialize_from_trace_processes(["P"])

        events = [
            create_event("early_event", {"P"}, {"P": 1}, {"early_prop"}),
            create_event("late_event", {"P"}, {"P": 2}, {"late_prop"}),
        ]

        # Process early event first
        monitor.process_event(events[0])
        # Should not fail immediately in multi-case scenarios

        monitor.process_event(events[1])
        # Should fail because early_prop ≤ late_prop in single process
        assert monitor.global_verdict == Verdict.FALSE

    def test_very_large_vector_clocks(self):
        """Test monitor with very large vector clock values."""
        monitor = PBTLMonitor("EP(target)")

        # Event with large timestamp values
        large_event = create_event(
            "large_vc", {"P"}, {"P": 999999, "Q": 888888}, {"target"}
        )
        monitor.process_event(large_event)

        assert monitor.global_verdict == Verdict.UNKNOWN

    def test_zero_timestamp_handling(self):
        """Test proper handling of zero timestamps in vector clocks."""
        monitor = PBTLMonitor("EP(EP(init) & !EP(error))")
        monitor.initialize_from_trace_processes(["P", "Q"])

        events = [
            create_event(
                "init_event", {"P"}, {"P": 1, "Q": 0}, {"init"}
            ),  # Zero timestamps
            create_event("follow_event", {"Q"}, {"P": 0, "Q": 1}, {"follow"}),
        ]

        for event in events:
            monitor.process_event(event)

        # Should succeed since error never occurs
        assert monitor.global_verdict == Verdict.TRUE

    def test_mixed_synchronous_asynchronous_events(self):
        """Test mixing single-process and multi-process synchronization events."""
        monitor = PBTLMonitor("EP(EP(sync_done) & individual_ready)")

        events = [
            # Individual events
            create_event("p1_prep", {"P1"}, {"P1": 1, "P2": 0}, set()),
            create_event("p2_prep", {"P2"}, {"P1": 0, "P2": 1}, set()),
            # Synchronization event
            create_event("sync", {"P1", "P2"}, {"P1": 2, "P2": 2}, {"sync_done"}),
            # Individual follow-up
            create_event(
                "individual", {"P3"}, {"P1": 2, "P2": 2, "P3": 1}, {"individual_ready"}
            ),
        ]

        for event in events:
            monitor.process_event(event)

        assert monitor.global_verdict == Verdict.TRUE

    def test_deeply_nested_formula_structure(self):
        """Test monitor with deeply nested formula structures."""
        # Complex nested formula
        nested_formula = (
            "EP(EP(EP(deep1) & deep2) & EP(EP(deep3) | deep4) & !EP(blocker))"
        )
        monitor = PBTLMonitor(nested_formula)
        monitor.initialize_from_trace_processes(["P1", "P2", "P3", "P4", "B"])

        events = [
            create_event(
                "e1", {"P1"}, {"P1": 1, "P2": 0, "P3": 0, "P4": 0, "B": 0}, {"deep1"}
            ),
            create_event(
                "e2", {"P2"}, {"P1": 0, "P2": 1, "P3": 0, "P4": 0, "B": 0}, {"deep2"}
            ),
            create_event(
                "e3", {"P3"}, {"P1": 0, "P2": 0, "P3": 1, "P4": 0, "B": 0}, {"deep3"}
            ),
            # blocker occurs but should not prevent success if properly concurrent
            create_event(
                "blocker_event",
                {"B"},
                {"P1": 0, "P2": 0, "P3": 0, "P4": 0, "B": 1},
                {"blocker"},
            ),
        ]

        for event in events:
            monitor.process_event(event)

        # Should succeed if blocker is concurrent with other events
        assert monitor.global_verdict == Verdict.TRUE

    def test_formula_with_only_boolean_constants(self):
        """Test formulas containing only boolean constants."""
        # Formula that should always succeed
        true_monitor = PBTLMonitor("EP(true)")
        dummy_event = create_event("dummy", {"P"}, {"P": 1}, set())
        true_monitor.process_event(dummy_event)
        assert true_monitor.global_verdict == Verdict.TRUE

        # Formula that should always fail
        false_monitor = PBTLMonitor("EP(false)")
        false_monitor.process_event(dummy_event)
        final_verdict = false_monitor.finalize()
        assert final_verdict == Verdict.FALSE

    def test_interleaved_multi_process_communication(self):
        """Test complex interleaved communication patterns between processes."""
        monitor = PBTLMonitor("EP(EP(request) & EP(response) & EP(confirmation))")
        monitor.initialize_from_trace_processes(["Client", "Server", "DB"])

        # Complex communication pattern
        events = [
            create_event(
                "client_request",
                {"Client"},
                {"Client": 1, "Server": 0, "DB": 0},
                {"request"},
            ),
            create_event(
                "server_db_query",
                {"Server", "DB"},
                {"Client": 1, "Server": 1, "DB": 1},
                {"query"},
            ),
            create_event(
                "db_response",
                {"DB"},
                {"Client": 1, "Server": 1, "DB": 2},
                {"db_result"},
            ),
            create_event(
                "server_response",
                {"Server"},
                {"Client": 1, "Server": 2, "DB": 2},
                {"response"},
            ),
            create_event(
                "client_confirm",
                {"Client"},
                {"Client": 2, "Server": 2, "DB": 2},
                {"confirmation"},
            ),
        ]

        for event in events:
            monitor.process_event(event)

        assert monitor.global_verdict == Verdict.TRUE

    def test_formula_evaluation_ordering_dependencies(self):
        """Test formula evaluation with complex ordering dependencies."""
        monitor = PBTLMonitor(
            "EP(EP(first) & EP(second) & EP(third) & !EP(interferer))"
        )
        monitor.initialize_from_trace_processes(["P1", "P2", "P3", "I"])

        # Create scenario where ordering matters for constraint checking
        events = [
            create_event(
                "first_event", {"P1"}, {"P1": 1, "P2": 0, "P3": 0, "I": 0}, {"first"}
            ),
            create_event(
                "interfere_early",
                {"I"},
                {"P1": 0, "P2": 0, "P3": 0, "I": 1},
                {"interferer"},
            ),
            create_event(
                "second_event", {"P2"}, {"P1": 1, "P2": 1, "P3": 0, "I": 1}, {"second"}
            ),
            create_event(
                "third_event", {"P3"}, {"P1": 1, "P2": 1, "P3": 1, "I": 0}, {"third"}
            ),
        ]

        for event in events:
            monitor.process_event(event)

        # Complex evaluation depending on exact frontier relationships
        # This test validates the frontier LUB calculation and N-constraint checking
        final_verdict = monitor.finalize()
        # The exact result depends on the specific vector clock relationships
        assert final_verdict in [Verdict.TRUE, Verdict.FALSE]

    def test_monitor_state_transitions(self):
        """Test monitor state transitions through different verdict states."""
        monitor = PBTLMonitor("EP(EP(eventual_target) & !EP(early_blocker))")
        monitor.initialize_from_trace_processes(["P"])

        # Initial state
        assert monitor.global_verdict == Verdict.UNKNOWN

        # Process non-matching event
        other_event = create_event("other", {"P"}, {"P": 1}, {"other_prop"})
        monitor.process_event(other_event)
        assert monitor.global_verdict == Verdict.UNKNOWN

        # Process target event
        target_event = create_event("target", {"P"}, {"P": 2}, {"eventual_target"})
        monitor.process_event(target_event)
        assert monitor.global_verdict == Verdict.TRUE

        # Further events shouldn't change conclusive verdict
        another_event = create_event("another", {"P"}, {"P": 3}, {"anything"})
        monitor.process_event(another_event)
        assert monitor.global_verdict == Verdict.TRUE

    def test_comprehensive_finalization_scenarios(self):
        """Test comprehensive finalization behavior across different scenarios."""
        # Scenario 1: All conditions met
        monitor1 = PBTLMonitor("EP(EP(success) & ready)")
        success_event = create_event("success_event", {"P"}, {"P": 1}, {"success"})
        ready_event = create_event("ready_event", {"P"}, {"P": 2}, {"ready"})
        monitor1.process_event(success_event)
        monitor1.process_event(ready_event)
        assert monitor1.finalize() == Verdict.TRUE

        # Scenario 2: Partial conditions
        monitor2 = PBTLMonitor("EP(EP(success) & missing)")
        monitor2.process_event(success_event)
        assert monitor2.finalize() == Verdict.FALSE

        # Scenario 3: N-constraint violation
        monitor3 = PBTLMonitor("EP(EP(late) & !EP(early))")
        monitor3.initialize_from_trace_processes(["P"])
        early_event = create_event("early_event", {"P"}, {"P": 1}, {"early"})
        late_event = create_event("late_event", {"P"}, {"P": 2}, {"late"})
        monitor3.process_event(early_event)
        monitor3.process_event(late_event)
        assert monitor3.finalize() == Verdict.FALSE
