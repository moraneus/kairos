# tests/core_tests/test_frontier_scenarios.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Comprehensive tests for Frontier model representing global states

"""Test suite for Frontier model covering global state representation and causal consistency.

This module provides comprehensive testing of the Frontier class functionality, including:
- Basic frontier creation and property access
- Vector clock computation for global states
- Frontier extension with new events
- Causal ordering between global states
- Complex multi-process scenarios
- Edge cases and causality patterns

The tests ensure correct implementation of the global state model that enables
proper evaluation of temporal properties in distributed system monitoring.
"""

import pytest
from core.event import Event, VectorClock
from core.frontier import Frontier


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


class TestFrontierBasicOperations:
    """Test basic Frontier operations and properties."""

    def test_frontier_creation_single_process(self):
        """Verify single-process frontier creation and access."""
        event = create_event("e1", {"P"}, {"P": 1}, {"ready"})
        frontier = Frontier({"P": event})

        assert "P" in frontier.events_dict
        assert frontier.events_dict["P"] == event
        assert len(frontier.events_dict) == 1

    def test_frontier_creation_multiple_processes(self):
        """Verify multi-process frontier creation."""
        event_p = create_event("ep", {"P"}, {"P": 1}, {"p_prop"})
        event_q = create_event("eq", {"Q"}, {"Q": 1}, {"q_prop"})

        frontier = Frontier({"P": event_p, "Q": event_q})

        assert len(frontier.events_dict) == 2
        assert frontier.events_dict["P"] == event_p
        assert frontier.events_dict["Q"] == event_q

    def test_frontier_vector_clock_computation(self):
        """Test component-wise maximum vector clock computation for frontiers.

        Verifies that frontier vector clocks correctly preserve the complete
        causal context by taking the component-wise maximum across all events.
        """
        # Event on P that knows about Q:2
        event_p = create_event("ep", {"P"}, {"P": 3, "Q": 2}, {"p_done"})
        # Event on Q that knows about P:1
        event_q = create_event("eq", {"Q"}, {"P": 1, "Q": 4}, {"q_done"})

        frontier = Frontier({"P": event_p, "Q": event_q})

        # Frontier VC should be component-wise maximum:
        # P: max(3, 1) = 3, Q: max(2, 4) = 4
        expected_vc = VectorClock({"P": 3, "Q": 4})
        assert frontier.vc == expected_vc

    def test_frontier_vector_clock_with_additional_processes(self):
        """Test frontier VC computation when events reference external processes."""
        # P knows about R:5
        event_p = create_event("ep", {"P"}, {"P": 2, "R": 5}, set())
        # Q knows about R:3
        event_q = create_event("eq", {"Q"}, {"Q": 1, "R": 3}, set())

        frontier = Frontier({"P": event_p, "Q": event_q})

        # Should include R with max(5, 3) = 5
        expected_vc = VectorClock({"P": 2, "Q": 1, "R": 5})
        assert frontier.vc == expected_vc

    def test_has_prop_method(self):
        """Test proposition checking across all events in frontier."""
        event_p = create_event("ep", {"P"}, {"P": 1}, {"prop_p", "shared"})
        event_q = create_event("eq", {"Q"}, {"Q": 1}, {"prop_q", "shared"})

        frontier = Frontier({"P": event_p, "Q": event_q})

        assert frontier.has_prop("prop_p") is True
        assert frontier.has_prop("prop_q") is True
        assert frontier.has_prop("shared") is True
        assert frontier.has_prop("not_present") is False

    def test_frontier_extend_with_event_single_process(self):
        """Test extending frontier with event for existing process."""
        initial_event = create_event("e1", {"P"}, {"P": 1}, {"initial"})
        frontier1 = Frontier({"P": initial_event})

        new_event = create_event("e2", {"P"}, {"P": 2}, {"updated"})
        frontier2 = frontier1.extend_with_event(new_event)

        # New frontier should have updated P's event
        assert frontier2.events_dict["P"] == new_event
        assert frontier2.has_prop("updated")
        assert not frontier2.has_prop("initial")

    def test_frontier_extend_with_event_multi_process(self):
        """Test extending frontier with synchronization event."""
        event_p = create_event("ep", {"P"}, {"P": 1}, set())
        event_q = create_event("eq", {"Q"}, {"Q": 1}, set())
        frontier1 = Frontier({"P": event_p, "Q": event_q})

        # Joint event updates both P and Q
        joint_event = create_event("sync", {"P", "Q"}, {"P": 2, "Q": 2}, {"synced"})
        frontier2 = frontier1.extend_with_event(joint_event)

        assert frontier2.events_dict["P"] == joint_event
        assert frontier2.events_dict["Q"] == joint_event
        assert frontier2.has_prop("synced")

    def test_frontier_extend_adding_new_process(self):
        """Test extending frontier by adding event for new process."""
        event_p = create_event("ep", {"P"}, {"P": 1}, set())
        frontier1 = Frontier({"P": event_p})

        event_q = create_event("eq", {"Q"}, {"Q": 1}, {"new_proc"})
        frontier2 = frontier1.extend_with_event(event_q)

        assert len(frontier2.events_dict) == 2
        assert frontier2.events_dict["P"] == event_p  # Unchanged
        assert frontier2.events_dict["Q"] == event_q  # Added
        assert frontier2.has_prop("new_proc")


class TestFrontierComparison:
    """Test frontier comparison and causal ordering."""

    def test_frontier_ordering_basic(self):
        """Test basic frontier ordering using vector clock comparison."""
        frontier1 = Frontier({"P": create_event("e1", {"P"}, {"P": 1}, set())})
        frontier2 = Frontier({"P": create_event("e2", {"P"}, {"P": 2}, set())})

        assert frontier1 < frontier2
        assert frontier1 <= frontier2
        assert not (frontier2 < frontier1)
        assert frontier2 > frontier1
        assert frontier2 >= frontier1

    def test_frontier_ordering_multi_process(self):
        """Test frontier ordering with multiple processes."""
        # Frontier where both P and Q are at timestamp 1
        f1_events = {
            "P": create_event("ep1", {"P"}, {"P": 1}, set()),
            "Q": create_event("eq1", {"Q"}, {"Q": 1}, set()),
        }
        frontier1 = Frontier(f1_events)

        # Frontier where P advances to 2, Q stays at 1
        f2_events = {
            "P": create_event("ep2", {"P"}, {"P": 2}, set()),
            "Q": create_event("eq1", {"Q"}, {"Q": 1}, set()),
        }
        frontier2 = Frontier(f2_events)

        assert frontier1 < frontier2
        assert frontier1 <= frontier2

    def test_concurrent_frontiers(self):
        """Test detection of concurrent frontiers (no causal ordering)."""
        # P advances, Q stays at initial
        frontier_p = Frontier({"P": create_event("ep", {"P"}, {"P": 1}, set())})

        # Q advances, P stays at initial
        frontier_q = Frontier({"Q": create_event("eq", {"Q"}, {"Q": 1}, set())})

        assert not (frontier_p < frontier_q)
        assert not (frontier_q < frontier_p)
        assert not (frontier_p <= frontier_q)
        assert not (frontier_q <= frontier_p)

    def test_frontier_equality(self):
        """Test frontier equality semantics."""
        event_p = create_event("ep", {"P"}, {"P": 1}, {"prop"})
        event_q = create_event("eq", {"Q"}, {"Q": 1}, {"prop"})

        frontier1 = Frontier({"P": event_p, "Q": event_q})
        frontier2 = Frontier({"P": event_p, "Q": event_q})
        frontier3 = Frontier({"Q": event_q, "P": event_p})  # Different order

        assert frontier1 == frontier2
        assert frontier1 == frontier3  # Order shouldn't matter
        assert hash(frontier1) == hash(frontier2)

    def test_frontier_reflexive_comparison(self):
        """Test reflexive properties of frontier comparison."""
        frontier = Frontier({"P": create_event("e1", {"P"}, {"P": 1}, set())})

        assert frontier <= frontier
        assert frontier >= frontier
        assert not (frontier < frontier)
        assert not (frontier > frontier)


class TestFrontierComplexScenarios:
    """Test complex frontier scenarios and edge cases."""

    def test_frontier_with_joint_events(self):
        """Test frontier containing multi-process synchronization events."""
        # Joint event involving P and Q
        joint_event = create_event(
            "sync", {"P", "Q"}, {"P": 2, "Q": 2}, {"synchronized"}
        )
        # Separate event for R
        r_event = create_event("er", {"R"}, {"R": 1}, {"r_prop"})

        frontier = Frontier({"P": joint_event, "Q": joint_event, "R": r_event})

        assert frontier.events_dict["P"] == joint_event
        assert frontier.events_dict["Q"] == joint_event
        assert frontier.events_dict["R"] == r_event
        assert frontier.has_prop("synchronized")
        assert frontier.has_prop("r_prop")

    def test_frontier_vector_clock_with_joint_events(self):
        """Test vector clock computation with complex joint events."""
        # Joint event with complex vector clock
        joint_event = create_event(
            "complex", {"P", "Q"}, {"P": 3, "Q": 2, "R": 1, "S": 4}, {"joint_prop"}
        )
        # Event on R that knows about different processes
        r_event = create_event(
            "er", {"R"}, {"P": 1, "Q": 1, "R": 2, "T": 1}, {"r_prop"}
        )

        frontier = Frontier({"P": joint_event, "Q": joint_event, "R": r_event})

        # Expected: component-wise maximum across all process knowledge
        expected_vc = VectorClock({"P": 3, "Q": 2, "R": 2, "S": 4, "T": 1})
        assert frontier.vc == expected_vc

    def test_empty_frontier(self):
        """Test empty frontier edge case."""
        frontier = Frontier({})

        assert len(frontier.events_dict) == 0
        assert frontier.vc == VectorClock({})
        assert not frontier.has_prop("anything")

    def test_frontier_string_representation(self):
        """Test string formatting for debugging and display."""
        # Empty frontier
        empty_frontier = Frontier({})
        assert str(empty_frontier) == "⟨empty⟩"

        # Single process frontier
        event = create_event("e1", {"P"}, {"P": 1}, set())
        single_frontier = Frontier({"P": event})
        assert "P:e1" in str(single_frontier)

        # Multi-process frontier (should be sorted by process name)
        event_p = create_event("ep", {"P"}, {"P": 1}, set())
        event_q = create_event("eq", {"Q"}, {"Q": 1}, set())
        event_r = create_event("er", {"R"}, {"R": 1}, set())
        multi_frontier = Frontier({"R": event_r, "P": event_p, "Q": event_q})

        frontier_str = str(multi_frontier)
        # Should be sorted: P, Q, R
        p_pos = frontier_str.find("P:")
        q_pos = frontier_str.find("Q:")
        r_pos = frontier_str.find("R:")
        assert p_pos < q_pos < r_pos

    def test_frontier_sequence_building_causality(self):
        """Test causal relationship building through frontier sequences."""
        # Start with initial frontier
        initial_event_p = create_event("init_p", {"P"}, {"P": 0}, {"iota"})
        initial_event_q = create_event("init_q", {"Q"}, {"Q": 0}, {"iota"})

        f0 = Frontier({"P": initial_event_p, "Q": initial_event_q})

        # P advances
        p1_event = create_event("p1", {"P"}, {"P": 1}, {"p_ready"})
        f1 = f0.extend_with_event(p1_event)

        # Q advances
        q1_event = create_event("q1", {"Q"}, {"Q": 1}, {"q_ready"})
        f2 = f1.extend_with_event(q1_event)

        # Joint synchronization
        sync_event = create_event("sync", {"P", "Q"}, {"P": 2, "Q": 2}, {"synced"})
        f3 = f2.extend_with_event(sync_event)

        # Verify causal chain
        assert f0 < f1 < f2 < f3
        assert f0.has_prop("iota")
        assert f1.has_prop("p_ready")
        assert f2.has_prop("q_ready")
        assert f3.has_prop("synced")

    def test_frontier_props_from_multiple_events(self):
        """Test proposition aggregation from multiple events."""
        event_p = create_event("ep", {"P"}, {"P": 1}, {"prop_p", "shared_prop"})
        event_q = create_event("eq", {"Q"}, {"Q": 1}, {"prop_q", "shared_prop"})
        event_r = create_event("er", {"R"}, {"R": 1}, {"prop_r"})

        frontier = Frontier({"P": event_p, "Q": event_q, "R": event_r})

        # Should find props from any event in the frontier
        assert frontier.has_prop("prop_p")
        assert frontier.has_prop("prop_q")
        assert frontier.has_prop("prop_r")
        assert frontier.has_prop("shared_prop")  # From multiple events
        assert not frontier.has_prop("nonexistent")

    def test_frontier_ordering_complex_vector_clocks(self):
        """Test frontier ordering with complex causal relationships."""
        # F1: P and Q have progressed independently
        f1_events = {
            "P": create_event("ep1", {"P"}, {"P": 2, "Q": 0}, set()),
            "Q": create_event("eq1", {"Q"}, {"P": 0, "Q": 2}, set()),
        }
        frontier1 = Frontier(f1_events)

        # F2: After synchronization - both know about each other
        f2_events = {
            "P": create_event("ep2", {"P"}, {"P": 3, "Q": 2}, set()),
            "Q": create_event("eq2", {"Q"}, {"P": 2, "Q": 3}, set()),
        }
        frontier2 = Frontier(f2_events)

        # F1 VC: [P:2, Q:2], F2 VC: [P:3, Q:3] -> F1 < F2
        assert frontier1 < frontier2

    def test_frontier_immutability(self):
        """Test frontier immutability - extending creates new instances."""
        original_event = create_event("orig", {"P"}, {"P": 1}, {"original"})
        original_frontier = Frontier({"P": original_event})

        new_event = create_event("new", {"P"}, {"P": 2}, {"updated"})
        extended_frontier = original_frontier.extend_with_event(new_event)

        # Original frontier should be unchanged
        assert original_frontier.events_dict["P"] == original_event
        assert original_frontier.has_prop("original")
        assert not original_frontier.has_prop("updated")

        # Extended frontier should have new event
        assert extended_frontier.events_dict["P"] == new_event
        assert not extended_frontier.has_prop("original")
        assert extended_frontier.has_prop("updated")

        # They should be different objects
        assert original_frontier != extended_frontier

    def test_frontier_with_partial_process_knowledge(self):
        """Test frontier behavior with partial vector clock knowledge."""
        # Event P knows about Q but not R
        event_p = create_event("ep", {"P"}, {"P": 2, "Q": 1}, {"p_prop"})
        # Event Q knows about R but not P's latest
        event_q = create_event("eq", {"Q"}, {"Q": 2, "R": 1}, {"q_prop"})
        # Event R only knows about itself
        event_r = create_event("er", {"R"}, {"R": 2}, {"r_prop"})

        frontier = Frontier({"P": event_p, "Q": event_q, "R": event_r})

        # Frontier VC should be component-wise maximum
        expected_vc = VectorClock({"P": 2, "Q": 2, "R": 2})
        assert frontier.vc == expected_vc

    def test_frontier_debug_string(self):
        """Test detailed debug string representation."""
        event = create_event("debug_event", {"P"}, {"P": 5}, {"test_prop"})
        frontier = Frontier({"P": event})

        debug_str = frontier.debug_str()
        assert "debug_event" in debug_str
        assert "VC:" in debug_str
        assert "[P:5]" in debug_str

    def test_frontier_with_zero_timestamps(self):
        """Test frontier handling of zero timestamps."""
        event_p = create_event("ep", {"P"}, {"P": 0}, {"initial"})
        event_q = create_event("eq", {"Q"}, {"Q": 0}, {"initial"})

        frontier = Frontier({"P": event_p, "Q": event_q})

        assert frontier.vc == VectorClock({"P": 0, "Q": 0})
        assert frontier.has_prop("initial")

    def test_frontier_process_events_consistency(self):
        """Test that frontier events tuple is properly sorted and accessible."""
        event_z = create_event("ez", {"Z"}, {"Z": 1}, set())
        event_a = create_event("ea", {"A"}, {"A": 1}, set())
        event_m = create_event("em", {"M"}, {"M": 1}, set())

        # Create with unsorted process order
        frontier = Frontier({"Z": event_z, "A": event_a, "M": event_m})

        # Events tuple should be sorted by process name
        process_order = [proc for proc, _ in frontier.events]
        assert process_order == ["A", "M", "Z"]

        # events_dict should have all processes
        assert len(frontier.events_dict) == 3
        assert "A" in frontier.events_dict
        assert "M" in frontier.events_dict
        assert "Z" in frontier.events_dict
