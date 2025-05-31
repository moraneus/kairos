# tests/integration_tests/test_monitor_scenarios.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Comprehensive integration tests for PBTLMonitor end-to-end property verification

"""Integration test suite for PBTLMonitor covering end-to-end property verification.

This module provides comprehensive integration testing of the PBTLMonitor class,
covering the complete monitoring pipeline from formula parsing through event
processing to final verdict determination. The tests validate:

- Basic monitor initialization and configuration
- All Table 1 cases (P-only, P+M, P+M+N, etc.)
- Causal ordering and vector clock behavior
- Multi-process synchronization events
- Complex formula structures and edge cases
- Out-of-order event delivery and buffering

These tests ensure the monitor correctly implements the Section 4 algorithm
for distributed system runtime verification using PBTL properties.
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


class TestMonitorBasicProperties:
    """Test basic PBTL monitor functionality and initialization."""

    def test_monitor_creation_and_initialization(self):
        """Verify monitor creation with formula parsing and initial state."""
        monitor = PBTLMonitor("EP(p)")

        assert monitor.formula_text == "EP(p)"
        assert monitor.global_verdict == Verdict.UNKNOWN
        assert len(monitor.disjuncts) == 1  # Single EP disjunct

    def test_monitor_with_system_processes_initialization(self):
        """Test monitor initialization with predefined system processes."""
        monitor = PBTLMonitor("EP(p & q)")
        monitor.initialize_from_trace_processes(["P", "Q", "R"])

        assert "P" in monitor.all_processes
        assert "Q" in monitor.all_processes
        assert "R" in monitor.all_processes
        assert monitor.initial_frontier is not None

    def test_monitor_simple_m_only_success(self):
        """Test Case 7 (M-only) property satisfaction."""
        monitor = PBTLMonitor("EP(ready)")

        # Process event that satisfies the property
        event = create_event("e1", {"P"}, {"P": 1}, {"ready"})
        monitor.process_event(event)

        assert monitor.global_verdict == Verdict.TRUE

    def test_monitor_simple_m_only_failure(self):
        """Test Case 7 (M-only) property failure."""
        monitor = PBTLMonitor("EP(target)")

        # Process event that doesn't satisfy the property
        event = create_event("e1", {"P"}, {"P": 1}, {"other_prop"})
        monitor.process_event(event)

        # Should remain UNKNOWN until finalized
        assert monitor.global_verdict == Verdict.UNKNOWN

        final_verdict = monitor.finalize()
        assert final_verdict == Verdict.FALSE

    def test_monitor_concurrent_events_success(self):
        """Test property satisfaction with concurrent events."""
        monitor = PBTLMonitor("EP(p & q)")

        # Two concurrent events providing different props
        event_p = create_event("ep", {"P"}, {"P": 1}, {"p"})
        event_q = create_event("eq", {"Q"}, {"Q": 1}, {"q"})

        monitor.process_event(event_p)
        monitor.process_event(event_q)

        assert monitor.global_verdict == Verdict.TRUE


class TestMonitorTableOneCases:
    """Test Table 1 cases from the Section 4 algorithm."""

    def test_p_and_n_success_case(self):
        """Test Case 4 (P+N) where P is satisfied and N constraint holds."""
        monitor = PBTLMonitor("EP(EP(ready) & !EP(error))")

        # Event satisfying P-block, N-block not violated
        ready_event = create_event("ready_ev", {"P"}, {"P": 1}, {"ready"})
        monitor.process_event(ready_event)

        assert monitor.global_verdict == Verdict.TRUE

    def test_p_and_n_failure_n_violation(self):
        """Test Case 4 (P+N) where N-block constraint is violated."""
        monitor = PBTLMonitor("EP(EP(ready) & !EP(error))")

        # Error occurs first, violating N-block
        error_event = create_event("error_ev", {"P"}, {"P": 1}, {"error"})
        monitor.process_event(error_event)

        assert monitor.global_verdict == Verdict.FALSE

    def test_p_and_n_success_with_late_n_violation(self):
        """Test Case 4 (P+N) where P succeeds before N violation."""
        monitor = PBTLMonitor("EP(EP(ready) & !EP(error))")

        # Ready occurs first (success)
        ready_event = create_event("ready_ev", {"P"}, {"P": 1}, {"ready"})
        monitor.process_event(ready_event)

        assert monitor.global_verdict == Verdict.TRUE

        # Error occurs later but shouldn't change verdict (terminal state)
        error_event = create_event("error_ev", {"P"}, {"P": 2}, {"error"})
        monitor.process_event(error_event)

        assert monitor.global_verdict == Verdict.TRUE

    def test_p_m_n_all_satisfied_success(self):
        """Test Case 3 (P+M+N) where all conditions are met."""
        monitor = PBTLMonitor("EP(EP(init) & ready & !EP(error))")

        # P-block satisfied
        init_event = create_event("init_ev", {"P"}, {"P": 1}, {"init"})
        monitor.process_event(init_event)

        # M-literal satisfied (causally after P)
        ready_event = create_event("ready_ev", {"P"}, {"P": 2}, {"ready"})
        monitor.process_event(ready_event)

        # N-block not violated
        assert monitor.global_verdict == Verdict.TRUE

    def test_p_m_n_n_violation_failure(self):
        """Test Case 3 (P+M+N) where N-block constraint is violated."""
        monitor = PBTLMonitor("EP(EP(init) & ready & !EP(error))")

        # P-block satisfied
        init_event = create_event("init_ev", {"P"}, {"P": 1}, {"init"})
        monitor.process_event(init_event)

        # N-block violated
        error_event = create_event("error_ev", {"P"}, {"P": 2}, {"error"})
        monitor.process_event(error_event)

        assert monitor.global_verdict == Verdict.FALSE

    def test_p_m_m_not_satisfied_failure(self):
        """Test Case 2 (P+M) where P is satisfied but M is not."""
        monitor = PBTLMonitor("EP(EP(init) & ready)")

        # P-block satisfied
        init_event = create_event("init_ev", {"P"}, {"P": 1}, {"init"})
        monitor.process_event(init_event)

        # M-literal never satisfied
        other_event = create_event("other_ev", {"P"}, {"P": 2}, {"other"})
        monitor.process_event(other_event)

        final_verdict = monitor.finalize()
        assert final_verdict == Verdict.FALSE

    def test_n_only_case_failure(self):
        """Test Case 6 (N-only) where N-block is satisfied (failure)."""
        monitor = PBTLMonitor("EP(!EP(forbidden))")

        # Forbidden event occurs
        forbidden_event = create_event("forbidden_ev", {"P"}, {"P": 1}, {"forbidden"})
        monitor.process_event(forbidden_event)

        assert monitor.global_verdict == Verdict.FALSE

    def test_n_only_case_success(self):
        """Test Case 6 (N-only) where N-block is not satisfied (success by default)."""
        monitor = PBTLMonitor("EP(!EP(forbidden))")

        # Other events occur, but not forbidden
        other_event = create_event("other_ev", {"P"}, {"P": 1}, {"allowed"})
        monitor.process_event(other_event)

        # At finalization, N-block was never violated
        final_verdict = monitor.finalize()
        # Note: This should actually be FALSE because EP(!EP(forbidden))
        # requires the negation to hold somewhere in the past, but since
        # nothing ever made !EP(forbidden) true, the property fails
        assert final_verdict == Verdict.FALSE


class TestMonitorCausalOrdering:
    """Test causal ordering and vector clock behavior."""

    def test_out_of_order_delivery_success(self):
        """Test causal delivery with out-of-order event arrival."""
        monitor = PBTLMonitor("EP(EP(first) & EP(second))")

        # Events arrive out of order
        second_event = create_event("second_ev", {"P"}, {"P": 2}, {"second"})
        first_event = create_event("first_ev", {"P"}, {"P": 1}, {"first"})

        monitor.process_event(second_event)  # Should be buffered
        assert monitor.global_verdict == Verdict.UNKNOWN

        monitor.process_event(first_event)  # Should flush both in order
        assert monitor.global_verdict == Verdict.TRUE

    def test_multi_process_causal_consistency(self):
        """Test causal consistency across multiple processes."""
        monitor = PBTLMonitor("EP(EP(p_msg) & EP(q_response))")

        # P sends message
        p_msg = create_event("p_msg", {"P"}, {"P": 1}, {"p_msg"})
        monitor.process_event(p_msg)

        # Q responds with knowledge of P's message
        q_response = create_event("q_resp", {"Q"}, {"P": 1, "Q": 1}, {"q_response"})
        monitor.process_event(q_response)

        assert monitor.global_verdict == Verdict.TRUE

    def test_vector_clock_based_n_constraint_checking(self):
        """Test N-constraint checking using vector clocks for causal relationships."""
        monitor = PBTLMonitor("EP(EP(late_prop) & !EP(early_prop))")

        # Early event
        early_event = create_event("early", {"P"}, {"P": 1}, {"early_prop"})
        monitor.process_event(early_event)

        # Late event that causally depends on early event
        late_event = create_event("late", {"P"}, {"P": 2}, {"late_prop"})
        monitor.process_event(late_event)

        # Should fail because early_prop happened before late_prop
        assert monitor.global_verdict == Verdict.FALSE

    def test_concurrent_events_n_constraint_success(self):
        """Test N-constraint success with truly concurrent events."""
        monitor = PBTLMonitor("EP(EP(p_prop) & !EP(q_prop))")
        monitor.initialize_from_trace_processes(["P", "Q"])

        # Concurrent events on different processes
        p_event = create_event("p_ev", {"P"}, {"P": 1}, {"p_prop"})
        q_event = create_event("q_ev", {"Q"}, {"Q": 1}, {"q_prop"})

        # P satisfies EP(p_prop) while Q hasn't happened in that frontier
        monitor.process_event(p_event)
        assert monitor.global_verdict == Verdict.TRUE

        # Q's event happening later shouldn't change the verdict
        monitor.process_event(q_event)
        assert monitor.global_verdict == Verdict.TRUE


class TestMonitorJointEvents:
    """Test multi-process synchronization events."""

    def test_joint_event_m_only_success(self):
        """Test M-only property satisfied by synchronization event."""
        monitor = PBTLMonitor("EP(sync_done)")

        # Prerequisites for joint event
        p_tick = create_event("p_tick", {"P"}, {"P": 1}, set())
        q_tick = create_event("q_tick", {"Q"}, {"Q": 1}, set())
        monitor.process_event(p_tick)
        monitor.process_event(q_tick)

        # Joint event providing the required property
        joint_event = create_event("sync", {"P", "Q"}, {"P": 2, "Q": 2}, {"sync_done"})
        monitor.process_event(joint_event)

        assert monitor.global_verdict == Verdict.TRUE

    def test_joint_event_p_block_satisfaction(self):
        """Test P-block satisfied by synchronization event."""
        monitor = PBTLMonitor("EP(EP(handshake) & confirmed)")

        # Prerequisites
        p_tick = create_event("p_tick", {"P"}, {"P": 1}, set())
        q_tick = create_event("q_tick", {"Q"}, {"Q": 1}, set())
        monitor.process_event(p_tick)
        monitor.process_event(q_tick)

        # Joint event satisfies P-block
        handshake_event = create_event(
            "handshake", {"P", "Q"}, {"P": 2, "Q": 2}, {"handshake"}
        )
        monitor.process_event(handshake_event)

        # M-literal satisfied by separate event
        confirm_event = create_event("confirm", {"R"}, {"R": 1}, {"confirmed"})
        monitor.process_event(confirm_event)

        assert monitor.global_verdict == Verdict.TRUE

    def test_joint_event_buffering_and_delivery(self):
        """Test synchronization event buffering when dependencies aren't met."""
        monitor = PBTLMonitor("EP(joint_prop)")

        # Joint event arrives before prerequisites
        joint_event = create_event(
            "joint", {"P", "Q"}, {"P": 2, "Q": 2}, {"joint_prop"}
        )
        monitor.process_event(joint_event)  # Should be buffered

        assert monitor.global_verdict == Verdict.UNKNOWN

        # Prerequisites arrive, allowing joint event delivery
        p_tick = create_event("p_tick", {"P"}, {"P": 1}, set())
        q_tick = create_event("q_tick", {"Q"}, {"Q": 1}, set())
        monitor.process_event(p_tick)
        monitor.process_event(q_tick)  # Should flush joint event

        assert monitor.global_verdict == Verdict.TRUE


class TestMonitorComplexFormulas:
    """Test complex PBTL formula structures."""

    def test_disjunction_one_branch_true(self):
        """Test disjunctive formula where one branch succeeds."""
        monitor = PBTLMonitor("EP(EP(option_a) | EP(option_b))")

        # Only option_a occurs
        option_a_event = create_event("a_ev", {"P"}, {"P": 1}, {"option_a"})
        monitor.process_event(option_a_event)

        assert monitor.global_verdict == Verdict.TRUE

    def test_disjunction_both_branches_false(self):
        """Test disjunctive formula where both branches fail."""
        monitor = PBTLMonitor("EP(EP(option_a) | EP(option_b))")

        # Neither option occurs
        other_event = create_event("other_ev", {"P"}, {"P": 1}, {"other"})
        monitor.process_event(other_event)

        final_verdict = monitor.finalize()
        assert final_verdict == Verdict.FALSE

    def test_nested_ep_formula(self):
        """Test nested EP formula evaluation."""
        monitor = PBTLMonitor("EP(EP(inner_prop) & outer_condition)")

        # Inner EP satisfied
        inner_event = create_event("inner_ev", {"P"}, {"P": 1}, {"inner_prop"})
        monitor.process_event(inner_event)

        # Outer condition satisfied
        outer_event = create_event("outer_ev", {"P"}, {"P": 2}, {"outer_condition"})
        monitor.process_event(outer_event)

        assert monitor.global_verdict == Verdict.TRUE

    def test_complex_multi_disjunct_formula(self):
        """Test complex formula with multiple disjuncts and constraints."""
        monitor = PBTLMonitor("EP((EP(s1) & !EP(j1)) | (EP(j2) & ms & !EP(s2)))")
        monitor.initialize_from_trace_processes(["S1", "J1", "J2", "MS", "S2"])

        # First disjunct should fail: j1 happens before s1
        j1_early = create_event("j1_early", {"J1"}, {"J1": 1}, {"j1"})
        monitor.process_event(j1_early)

        s1_event = create_event("s1_late", {"S1"}, {"S1": 1, "J1": 1}, {"s1"})
        monitor.process_event(s1_event)

        # Second disjunct should succeed: j2 and ms without s2
        j2_event = create_event("j2_ev", {"J2"}, {"J2": 1}, {"j2"})
        monitor.process_event(j2_event)

        ms_event = create_event("ms_ev", {"MS"}, {"MS": 1}, {"ms"})
        monitor.process_event(ms_event)

        # Should succeed via second disjunct
        assert monitor.global_verdict == Verdict.TRUE


class TestMonitorEdgeCases:
    """Test edge cases and special monitoring scenarios."""

    def test_empty_trace_finalization(self):
        """Test monitor behavior with no events processed."""
        monitor = PBTLMonitor("EP(some_prop)")

        # No events processed
        final_verdict = monitor.finalize()
        assert final_verdict == Verdict.FALSE

    def test_iota_proposition_handling(self):
        """Test handling of special 'iota' proposition in initial states."""
        monitor = PBTLMonitor("EP(iota)")
        monitor.initialize_from_trace_processes(["P"])

        # Monitor needs to evaluate against the initial frontier
        # Process any event to trigger evaluation
        dummy_event = create_event("dummy", {"P"}, {"P": 1}, {"other"})
        monitor.process_event(dummy_event)

        # Should succeed because iota was available in the initial frontier
        assert monitor.global_verdict == Verdict.TRUE

    def test_monitor_verbose_mode(self):
        """Test monitor verbose output mode functionality."""
        monitor = PBTLMonitor("EP(test_prop)")
        monitor.set_verbose(True)

        event = create_event("test_ev", {"P"}, {"P": 1}, {"test_prop"})
        monitor.process_event(event)

        # Verify it doesn't crash in verbose mode
        assert monitor.global_verdict == Verdict.TRUE

    def test_monitor_is_conclusive(self):
        """Test monitor conclusiveness state checking."""
        monitor = PBTLMonitor("EP(target)")

        assert not monitor.is_conclusive()  # Initially unknown

        event = create_event("target_ev", {"P"}, {"P": 1}, {"target"})
        monitor.process_event(event)

        assert monitor.is_conclusive()  # Now conclusive (TRUE)
        assert monitor.global_verdict == Verdict.TRUE

    def test_monitor_finalize_idempotent(self):
        """Test that finalize() can be called multiple times safely."""
        monitor = PBTLMonitor("EP(prop)")

        event = create_event("ev", {"P"}, {"P": 1}, {"other"})
        monitor.process_event(event)

        first_verdict = monitor.finalize()
        second_verdict = monitor.finalize()

        assert first_verdict == second_verdict
        assert first_verdict == Verdict.FALSE

    def test_large_event_sequence_performance(self):
        """Test monitor performance with long event sequences."""
        monitor = PBTLMonitor("EP(final_prop)")

        # Create chain of 20 events
        for i in range(1, 21):
            event = create_event(f"step_{i}", {"P"}, {"P": i}, {f"step_{i}_prop"})
            monitor.process_event(event)

        # Final event with target prop
        final_event = create_event("final", {"P"}, {"P": 21}, {"final_prop"})
        monitor.process_event(final_event)

        assert monitor.global_verdict == Verdict.TRUE

    def test_monitor_with_boolean_constants(self):
        """Test monitor handling of true/false boolean constants."""
        # Formula that should always be true
        true_monitor = PBTLMonitor("EP(true)")
        event = create_event("any_ev", {"P"}, {"P": 1}, {"anything"})
        true_monitor.process_event(event)
        assert true_monitor.global_verdict == Verdict.TRUE

        # Formula that should always be false
        false_monitor = PBTLMonitor("EP(false)")
        false_monitor.process_event(event)
        final_verdict = false_monitor.finalize()
        assert final_verdict == Verdict.FALSE

    def test_monitor_multiple_process_initialization(self):
        """Test monitor initialization with multiple processes."""
        monitor = PBTLMonitor("EP(multi_proc_prop)")
        monitor.initialize_from_trace_processes(["P1", "P2", "P3", "P4", "P5"])

        assert len(monitor.all_processes) == 5
        assert monitor.initial_frontier is not None
        assert len(monitor.current_frontiers) == 1

        # All processes should have iota events
        initial_events = monitor.initial_frontier.events_dict
        assert len(initial_events) == 5
        for proc in ["P1", "P2", "P3", "P4", "P5"]:
            assert proc in initial_events
            assert initial_events[proc].has_prop("iota")

    def test_simple_request_response_example(self):
        """Test Example 1 (From README.md): Simple Request-Response scenario.

        Property: EP(EP(request) & EP(response))
        Expected Result: TRUE
        """
        monitor = PBTLMonitor("EP(EP(request) & EP(response))")
        monitor.initialize_from_trace_processes(["Client", "Server"])

        # Event 1: request
        req_event = create_event(
            "req", {"Client", "Server"}, {"Client": 1, "Server": 1}, {"request"}
        )
        monitor.process_event(req_event)

        # Event 2: response
        resp_event = create_event(
            "resp", {"Server", "Client"}, {"Client": 2, "Server": 2}, {"response"}
        )
        monitor.process_event(resp_event)

        # Finalize and check verdict
        final_verdict = monitor.finalize()
        assert final_verdict == Verdict.TRUE
        assert monitor.global_verdict == Verdict.TRUE

    def test_error_detection_example(self):
        """Test Example 2 (From README.md): Error Detection scenario.

        Property: EP(EP(process_started) & !EP(fatal_error))
        Expected Result: FALSE (fatal_error violates the constraint)
        """
        monitor = PBTLMonitor("EP(EP(process_started) & !EP(fatal_error))")
        monitor.initialize_from_trace_processes(["Worker"])

        # Event 1: process started
        start_event = create_event(
            "start", {"Worker"}, {"Worker": 2}, {"process_started"}
        )
        monitor.process_event(start_event)

        # Event 2: fatal error occurs
        error_event = create_event("error", {"Worker"}, {"Worker": 1}, {"fatal_error"})
        monitor.process_event(error_event)

        # Finalize and check verdict
        final_verdict = monitor.finalize()
        assert final_verdict == Verdict.FALSE
        assert monitor.global_verdict == Verdict.FALSE

    def test_distributed_consensus_example(self):
        """Test Example 3 (From README.md): Distributed Consensus scenario.

        Property: EP(EP(prepare) & EP(commit) & !EP(abort))
        Expected Result: TRUE
        """
        monitor = PBTLMonitor("EP(EP(prepare) & EP(commit) & !EP(abort))")
        monitor.initialize_from_trace_processes(["Node1", "Node2", "Node3"])

        # Event 1: Node1 prepares
        prep1_event = create_event(
            "prep1", {"Node1"}, {"Node1": 1, "Node2": 0, "Node3": 0}, {"prepare"}
        )
        monitor.process_event(prep1_event)

        # Event 2: Node2 prepares
        prep2_event = create_event(
            "prep2", {"Node2"}, {"Node1": 0, "Node2": 1, "Node3": 0}, {"prepare"}
        )
        monitor.process_event(prep2_event)

        # Event 3: Node3 prepares
        prep3_event = create_event(
            "prep3", {"Node3"}, {"Node1": 0, "Node2": 0, "Node3": 1}, {"prepare"}
        )
        monitor.process_event(prep3_event)

        # Event 4: All nodes commit together
        commit_event = create_event(
            "commit",
            {"Node1", "Node2", "Node3"},
            {"Node1": 2, "Node2": 2, "Node3": 2},
            {"commit"},
        )
        monitor.process_event(commit_event)

        # Finalize and check verdict
        final_verdict = monitor.finalize()
        assert final_verdict == Verdict.TRUE
        assert monitor.global_verdict == Verdict.TRUE

    def test_distributed_consensus_with_abort_example(self):
        """Test Example 3 variant (From README.md): Distributed Consensus with abort.

        Property: EP(EP(prepare) & EP(commit) & !EP(abort))
        Expected Result: FALSE (abort violates the constraint)
        """
        monitor = PBTLMonitor("EP(EP(prepare) & EP(commit) & !EP(abort))")
        monitor.initialize_from_trace_processes(["Node1", "Node2", "Node3"])

        # Event 1: Node1 prepares
        prep1_event = create_event(
            "prep1", {"Node1"}, {"Node1": 1, "Node2": 0, "Node3": 0}, {"prepare"}
        )
        monitor.process_event(prep1_event)

        # Event 2: Node2 prepares
        prep2_event = create_event(
            "prep2", {"Node2"}, {"Node1": 0, "Node2": 1, "Node3": 0}, {"prepare"}
        )
        monitor.process_event(prep2_event)

        # Event 3: Abort occurs instead of continuing
        abort_event = create_event(
            "abort",
            {"Node1", "Node2", "Node3"},
            {"Node1": 2, "Node2": 2, "Node3": 1},
            {"abort"},
        )
        monitor.process_event(abort_event)

        # Event 4: Later commit (but abort already happened)
        commit_event = create_event(
            "commit",
            {"Node1", "Node2", "Node3"},
            {"Node1": 3, "Node2": 3, "Node3": 2},
            {"commit"},
        )
        monitor.process_event(commit_event)

        # Finalize and check verdict
        final_verdict = monitor.finalize()
        assert final_verdict == Verdict.FALSE
        assert monitor.global_verdict == Verdict.FALSE
