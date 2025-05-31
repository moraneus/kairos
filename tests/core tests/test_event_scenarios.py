# test/core_tests/test_event_scenarios.py
# This file is part of Kairos - Clean PBTL Runtime Verification
#
# Tests for Event model - creation, properties, and causal ordering

import pytest
from core.event import Event, VectorClock


def create_event(
    eid: str, procs: set[str], clock: dict[str, int], props: set[str]
) -> Event:
    """Factory for creating Event objects for testing."""
    return Event(eid, frozenset(procs), VectorClock(clock), frozenset(props))


class TestEventBasicProperties:
    """Test suite for basic Event properties and functionality."""

    def test_event_creation_single_process(self):
        """Test creating a simple single-process event."""
        event = create_event("e1", {"P"}, {"P": 1}, {"prop1", "prop2"})

        assert event.eid == "e1"
        assert event.processes == frozenset({"P"})
        assert event.vc == VectorClock({"P": 1})
        assert event.props == frozenset({"prop1", "prop2"})

    def test_event_creation_multi_process(self):
        """Test creating a multi-process (joint) event."""
        event = create_event("sync1", {"P", "Q"}, {"P": 2, "Q": 3}, {"sync"})

        assert event.eid == "sync1"
        assert event.processes == frozenset({"P", "Q"})
        assert event.vc == VectorClock({"P": 2, "Q": 3})
        assert event.props == frozenset({"sync"})

    def test_has_prop_method(self):
        """Test the has_prop method for checking proposition membership."""
        event = create_event("e1", {"P"}, {"P": 1}, {"p", "q", "ready"})

        assert event.has_prop("p") is True
        assert event.has_prop("q") is True
        assert event.has_prop("ready") is True
        assert event.has_prop("not_present") is False
        assert event.has_prop("") is False

    def test_event_with_no_props(self):
        """Test event with no propositions."""
        event = create_event("empty", {"P"}, {"P": 1}, set())

        assert event.props == frozenset()
        assert event.has_prop("anything") is False

    def test_event_equality_and_hashing(self):
        """Test event equality and hash consistency."""
        event1 = create_event("e1", {"P"}, {"P": 1}, {"prop"})
        event2 = create_event("e1", {"P"}, {"P": 1}, {"prop"})
        event3 = create_event("e2", {"P"}, {"P": 1}, {"prop"})  # Different eid

        assert event1 == event2
        assert hash(event1) == hash(event2)
        assert event1 != event3
        assert event1 != "not_an_event"

    def test_event_string_representation(self):
        """Test string representation of events."""
        event = create_event("test_event", {"P"}, {"P": 4}, {"ready"})
        event_str = str(event)

        assert "test_event" in event_str
        assert "P" in event_str
        assert "[P:4]" in event_str
        assert "ready" in event_str


class TestEventCausalOrdering:
    """Test suite for causal ordering between events."""

    def test_happens_before_same_process(self):
        """Test happens-before relationship for events on same process."""
        event1 = create_event("e1", {"P"}, {"P": 1}, set())
        event2 = create_event("e2", {"P"}, {"P": 2}, set())
        event3 = create_event("e3", {"P"}, {"P": 3}, set())

        assert event1 < event2
        assert event2 < event3
        assert event1 < event3  # Transitivity
        assert not (event2 < event1)
        assert event1 <= event2
        assert event2 >= event1

    def test_concurrent_events_different_processes(self):
        """Test concurrent events on different processes."""
        event_p = create_event("ep", {"P"}, {"P": 1}, set())
        event_q = create_event("eq", {"Q"}, {"Q": 1}, set())

        # Events are concurrent - neither happens before the other
        assert not (event_p < event_q)
        assert not (event_q < event_p)
        assert event_p != event_q

    def test_causal_dependency_across_processes(self):
        """Test causal dependency when events know about other processes."""
        # P's first event
        p1 = create_event("p1", {"P"}, {"P": 1}, set())

        # Q's event that knows about P's event
        q1_after_p = create_event("q1", {"Q"}, {"P": 1, "Q": 1}, set())

        assert p1 < q1_after_p

    def test_multi_process_event_causality(self):
        """Test causality with multi-process events."""
        # Independent events
        p1 = create_event("p1", {"P"}, {"P": 1}, set())
        q1 = create_event("q1", {"Q"}, {"Q": 1}, set())

        # Joint event that depends on both
        pq_sync = create_event("sync", {"P", "Q"}, {"P": 2, "Q": 2}, {"synced"})

        assert p1 < pq_sync
        assert q1 < pq_sync

    def test_complex_vector_clock_comparison(self):
        """Test complex vector clock comparisons."""
        # Event with knowledge of multiple processes
        event1 = create_event("e1", {"P"}, {"P": 3, "Q": 2, "R": 1}, set())
        event2 = create_event("e2", {"Q"}, {"P": 2, "Q": 3, "S": 1}, set())

        # These should be concurrent - neither dominates
        assert not (event1 < event2)
        assert not (event2 < event1)

    def test_reflexive_comparison(self):
        """Test reflexive properties of event comparison."""
        event = create_event("e1", {"P"}, {"P": 1}, {"prop"})

        assert event <= event
        assert event >= event
        assert not (event < event)
        assert not (event > event)


class TestEventComplexScenarios:
    """Test suite for complex event scenarios."""

    def test_event_with_complex_vector_clock(self):
        """Test event with vector clock involving multiple processes."""
        # Event on P that knows about Q and R
        event = create_event("complex", {"P"}, {"P": 5, "Q": 3, "R": 2}, {"data"})

        assert event.processes == frozenset({"P"})
        assert event.vc.clock_dict == {"P": 5, "Q": 3, "R": 2}
        assert event.has_prop("data")

    def test_multi_process_event_with_props(self):
        """Test multi-process event carrying multiple propositions."""
        event = create_event(
            "handshake", {"A", "B"}, {"A": 2, "B": 2}, {"ack", "ready", "synced"}
        )

        assert len(event.processes) == 2
        assert event.has_prop("ack")
        assert event.has_prop("ready")
        assert event.has_prop("synced")
        assert not event.has_prop("nack")

    def test_event_sequence_building_causality(self):
        """Test a sequence of events building causal relationships."""
        # Start with independent events
        events = []
        events.append(create_event("p1", {"P"}, {"P": 1}, {"init_p"}))
        events.append(create_event("q1", {"Q"}, {"Q": 1}, {"init_q"}))

        # P communicates with Q
        events.append(create_event("p2", {"P"}, {"P": 2, "Q": 1}, {"msg_to_q"}))

        # Q responds, knowing about P's message
        events.append(create_event("q2", {"Q"}, {"P": 2, "Q": 2}, {"response"}))

        # Verify causal relationships
        assert events[0] < events[2]  # p1 < p2
        assert events[1] < events[3]  # q1 < q2
        assert events[2] < events[3]  # p2 < q2 (causal dependency)

        # Initial events are concurrent
        assert not (events[0] < events[1])
        assert not (events[1] < events[0])

    def test_event_with_numeric_and_special_props(self):
        """Test events with various proposition types."""
        event = create_event(
            "special",
            {"P"},
            {"P": 1},
            {"123", "prop_with_underscore", "CAPS", "mixed_Case"},
        )

        assert event.has_prop("123")
        assert event.has_prop("prop_with_underscore")
        assert event.has_prop("CAPS")
        assert event.has_prop("mixed_Case")

    def test_event_prop_order_independence(self):
        """Test that proposition order doesn't affect equality."""
        event1 = create_event("e1", {"P"}, {"P": 1}, {"a", "b", "c"})
        event2 = create_event("e1", {"P"}, {"P": 1}, {"c", "a", "b"})

        assert event1 == event2
        assert hash(event1) == hash(event2)

    def test_event_process_order_independence(self):
        """Test that process order doesn't affect equality for multi-process events."""
        event1 = create_event(
            "sync", {"P", "Q", "R"}, {"P": 1, "Q": 1, "R": 1}, {"done"}
        )
        event2 = create_event(
            "sync", {"R", "P", "Q"}, {"P": 1, "Q": 1, "R": 1}, {"done"}
        )

        assert event1 == event2
        assert hash(event1) == hash(event2)

    def test_empty_process_set_event(self):
        """Test creating event with empty process set (edge case)."""
        event = create_event("orphan", set(), {}, {"isolated"})

        assert len(event.processes) == 0
        assert event.has_prop("isolated")
        assert event.vc == VectorClock({})

    def test_event_comparison_with_non_event(self):
        """Test that events are not equal to non-event objects."""
        event = create_event("e1", {"P"}, {"P": 1}, {"prop"})

        assert event != "string"
        assert event != 42
        assert event != None
        assert event != {"eid": "e1"}
        assert event != ["e1", "P", 1]
