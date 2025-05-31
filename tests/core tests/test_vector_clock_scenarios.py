# tests/test_vector_clock_scenarios.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Comprehensive tests for VectorClock causal ordering and happens-before relationships

"""Test suite for VectorClock model covering causal ordering in distributed systems.

This module provides comprehensive testing of the VectorClock class functionality, including:
- Basic happens-before relationships and causal ordering
- Concurrency detection between independent events
- Vector clock comparisons with partial process knowledge
- Complex multi-process causality scenarios
- Edge cases with zero timestamps and large values

The tests ensure correct implementation of Lamport's vector clock algorithm
that enables proper causal reasoning in distributed system monitoring.
"""

import pytest
from core.event import VectorClock


class TestVectorClockCausalOrdering:
    """Test VectorClock operations for causal ordering and concurrency detection."""

    def test_happens_before_basic_single_process(self):
        """Test basic happens-before relationship on single process."""
        vc1 = VectorClock({"P": 1})
        vc2 = VectorClock({"P": 2})

        assert vc1 < vc2
        assert vc1 <= vc2
        assert not (vc2 < vc1)
        assert not (vc2 <= vc1)
        assert vc1 != vc2

    def test_concurrent_events_different_processes(self):
        """Test detection of concurrent events on different processes."""
        vc_p = VectorClock({"P": 1})
        vc_q = VectorClock({"Q": 1})

        # Neither happens before the other - they're concurrent
        assert not (vc_p < vc_q)
        assert not (vc_q < vc_p)
        assert not (vc_p <= vc_q)
        assert not (vc_q <= vc_p)
        assert vc_p != vc_q

    def test_causal_dependency_across_processes(self):
        """Test causal dependency detection when one process knows about another."""
        # P knows about Q's timestamp 1, P advances to 2
        vc1 = VectorClock({"P": 1, "Q": 1})
        vc2 = VectorClock({"P": 2, "Q": 1})

        assert vc1 < vc2
        assert vc1 <= vc2

    def test_vector_clock_equality(self):
        """Test vector clock equality semantics and hash consistency."""
        vc1 = VectorClock({"P": 1, "Q": 2})
        vc2 = VectorClock({"P": 1, "Q": 2})
        vc3 = VectorClock({"Q": 2, "P": 1})  # Same content, different order

        assert vc1 == vc2
        assert vc1 == vc3
        assert hash(vc1) == hash(vc2)
        assert hash(vc1) == hash(vc3)

    def test_vector_clock_inequality_missing_process(self):
        """Test inequality when processes have different knowledge sets."""
        vc1 = VectorClock({"P": 1})
        vc2 = VectorClock({"P": 1, "Q": 1})

        # vc1 has less knowledge - missing Q timestamp treated as 0
        assert vc1 < vc2
        assert vc1 != vc2

    def test_concurrent_events_overlapping_processes(self):
        """Test concurrency detection with overlapping process knowledge."""
        vc1 = VectorClock({"P": 2, "Q": 1})
        vc2 = VectorClock({"P": 1, "Q": 2})

        # Neither dominates the other - concurrent
        assert not (vc1 < vc2)
        assert not (vc2 < vc1)
        assert not (vc1 <= vc2)
        assert not (vc2 <= vc1)

    def test_reflexivity_of_comparison(self):
        """Test reflexive properties of vector clock comparison operators."""
        vc = VectorClock({"P": 1, "Q": 2})

        assert vc <= vc
        assert vc >= vc
        assert not (vc < vc)
        assert not (vc > vc)

    def test_transitivity_of_happens_before(self):
        """Test transitivity property: if A ≤ B and B ≤ C, then A ≤ C."""
        vc1 = VectorClock({"P": 1, "Q": 1})
        vc2 = VectorClock({"P": 1, "Q": 2, "R": 1})
        vc3 = VectorClock({"P": 2, "Q": 2, "R": 1})

        assert vc1 <= vc2
        assert vc2 <= vc3
        assert vc1 <= vc3  # Transitivity

    def test_empty_vector_clock(self):
        """Test behavior with empty vector clocks (initial system state)."""
        vc_empty = VectorClock({})
        vc_non_empty = VectorClock({"P": 1})

        assert vc_empty <= vc_non_empty
        assert vc_empty < vc_non_empty
        assert vc_empty != vc_non_empty

    def test_string_representation(self):
        """Test string formatting for debugging and display."""
        vc_empty = VectorClock({})
        vc_single = VectorClock({"P": 5})
        vc_multi = VectorClock({"Q": 2, "P": 1, "R": 3})

        assert str(vc_empty) == "[]"
        assert str(vc_single) == "[P:5]"
        # Should be sorted by process name
        assert str(vc_multi) == "[P:1, Q:2, R:3]"

    def test_complex_multi_process_scenario(self):
        """Test complex causality scenario with synchronization patterns."""
        # Scenario: P and Q start independently, synchronize, then continue

        # Initial independent events
        p_initial = VectorClock({"P": 1})
        q_initial = VectorClock({"Q": 1})

        # After synchronization - both know about each other
        p_after_sync = VectorClock({"P": 2, "Q": 1})
        q_after_sync = VectorClock({"P": 1, "Q": 2})

        # Later events building on synchronization
        p_later = VectorClock({"P": 3, "Q": 2})

        # Verify causal relationships
        assert p_initial < p_after_sync
        assert q_initial < q_after_sync
        assert p_after_sync < p_later
        assert q_after_sync < p_later

        # Initial events are concurrent
        assert not (p_initial < q_initial)
        assert not (q_initial < p_initial)

    def test_vector_clock_with_zero_timestamps(self):
        """Test vector clocks with zero timestamps (system initialization)."""
        vc1 = VectorClock({"P": 0, "Q": 0})
        vc2 = VectorClock({"P": 1, "Q": 0})

        assert vc1 < vc2
        assert vc1 <= vc2

    def test_large_timestamp_values(self):
        """Test vector clocks with large timestamp values (long-running systems)."""
        vc1 = VectorClock({"P": 1000, "Q": 999})
        vc2 = VectorClock({"P": 1000, "Q": 1000})

        assert vc1 < vc2
        assert vc1 <= vc2

    def test_many_processes_scenario(self):
        """Test vector clocks with many processes (large distributed systems)."""
        processes = [f"P{i}" for i in range(10)]

        # All processes at timestamp 1
        vc1 = VectorClock({p: 1 for p in processes})

        # P0 advances to timestamp 2
        vc2_dict = {p: 1 for p in processes}
        vc2_dict["P0"] = 2
        vc2 = VectorClock(vc2_dict)

        assert vc1 < vc2
        assert vc1 <= vc2

    def test_vector_clock_immutability(self):
        """Test that vector clocks are properly immutable."""
        vc = VectorClock({"P": 1, "Q": 2})

        # Modifying clock_dict should not affect the original VectorClock
        # since clock_dict returns a new dictionary each time
        original_clock_dict = vc.clock_dict
        modified_dict = vc.clock_dict
        modified_dict["P"] = 5

        # Original should be unchanged
        assert vc.clock_dict == original_clock_dict
        assert vc.clock_dict["P"] == 1

        # Clock tuple should be immutable (read-only attribute)
        with pytest.raises(AttributeError):
            vc.clock = (("P", 5), ("Q", 2))

    def test_antisymmetric_property(self):
        """Test antisymmetric property: if A ≤ B and B ≤ A, then A = B."""
        vc1 = VectorClock({"P": 1, "Q": 2})
        vc2 = VectorClock({"P": 1, "Q": 2})

        assert vc1 <= vc2
        assert vc2 <= vc1
        assert vc1 == vc2

    def test_partial_order_properties(self):
        """Test that vector clock ordering forms a proper partial order."""
        vc1 = VectorClock({"P": 1})
        vc2 = VectorClock({"P": 1, "Q": 1})
        vc3 = VectorClock({"P": 2, "Q": 1})
        vc_concurrent = VectorClock({"R": 1})

        # Reflexivity: each VC ≤ itself
        assert vc1 <= vc1
        assert vc2 <= vc2
        assert vc3 <= vc3

        # Antisymmetry: if A ≤ B and B ≤ A, then A = B
        vc_copy = VectorClock({"P": 1})
        assert vc1 <= vc_copy and vc_copy <= vc1
        assert vc1 == vc_copy

        # Transitivity: if A ≤ B and B ≤ C, then A ≤ C
        assert vc1 <= vc2 <= vc3
        assert vc1 <= vc3

        # Incomparability: some elements are not comparable
        assert not (vc1 <= vc_concurrent)
        assert not (vc_concurrent <= vc1)

    def test_clock_dict_property(self):
        """Test clock_dict property provides correct dictionary access."""
        original_dict = {"P": 3, "Q": 1, "R": 2}
        vc = VectorClock(original_dict)

        # Should return equivalent dictionary
        assert vc.clock_dict == original_dict

        # Should handle empty case
        empty_vc = VectorClock({})
        assert empty_vc.clock_dict == {}

    def test_comparison_with_non_vector_clock(self):
        """Test vector clock comparison with non-VectorClock objects."""
        vc = VectorClock({"P": 1})

        # Should not be equal to non-VectorClock objects
        assert vc != "string"
        assert vc != {"P": 1}
        assert vc != [("P", 1)]
        assert vc != 42
        assert vc != None
