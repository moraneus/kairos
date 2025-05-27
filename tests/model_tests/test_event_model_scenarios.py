# test/model_tests/test_event_model_scenarios.py

import pytest
from model.event import Event
from model.vector_clock import VectorClock as VC


# Unified helper function for creating Event objects (as provided by user)
def E(eid: str, procs: set[str], clock: dict[str, int], props: set[str]) -> Event:
    """Factory for creating Event objects for testing."""
    return Event(eid, frozenset(procs), VC(clock), frozenset(props))


class TestEventModelScenarios:
    """
    Test suite for the Event data model, covering creation, property checking,
    equality, hashing, comparison (happens-before, concurrency), and string representation,
    including scenarios with single and multi-owner events.
    """

    # --- "Normal" Tests (Single-Owner Focus, Basic Properties) ---

    def test_01_has_and_prop_membership(self):
        """
        Tests the `has()` method for checking proposition membership.
        An event 'e1' on process 'P' at timestamp 1 carries props 'p' and 'q'.
        It should report `True` for 'p' and `False` for a non-existent prop 'x'.
        """
        e = E(eid='e1', procs={'P'}, clock={'P': 1}, props={'p', 'q'})
        assert e.has('p') is True
        assert e.has('q') is True
        assert e.has('x') is False

    def test_02_equality_and_hash_consistency(self):
        """
        Tests that two identical events are equal and have the same hash code.
        Events 'e1' and 'e2' are identical in all aspects.
        """
        e1 = E(eid='ev1', procs={'P'}, clock={'P': 1}, props={'p'})
        e2 = E(eid='ev1', procs={'P'}, clock={'P': 1}, props={'p'})
        e3_diff_eid = E(eid='ev2', procs={'P'}, clock={'P': 1}, props={'p'})
        e4_diff_proc = E(eid='ev1', procs={'Q'}, clock={'Q': 1}, props={'p'})  # proc in clock also changes
        e5_diff_ts = E(eid='ev1', procs={'P'}, clock={'P': 2}, props={'p'})
        e6_diff_prop = E(eid='ev1', procs={'P'}, clock={'P': 1}, props={'q'})

        assert e1 == e2
        assert hash(e1) == hash(e2)
        assert e1 != e3_diff_eid
        assert e1 != e4_diff_proc  # Also implies different VC content
        assert e1 != e5_diff_ts
        assert e1 != e6_diff_prop

    def test_03_diff_process_same_ts_are_concurrent(self):
        """
        Tests that events on different processes with the same local timestamp
        (but independent causal histories for those processes) are concurrent.
        Event 'e_p' on P@1, 'e_q' on Q@1.
        """
        e_p = E(eid='e_p', procs={'P'}, clock={'P': 1}, props=set())
        e_q = E(eid='e_q', procs={'Q'}, clock={'Q': 1}, props=set())
        assert e_p.concurrent(e_q)
        assert not (e_p < e_q)
        assert not (e_q < e_p)

    def test_04_happens_before_chain_on_same_process(self):
        """
        Tests the happens-before relationship (less than) for a sequence of events
        on the same process with increasing timestamps.
        e1@P:1 < e2@P:2 < e3@P:3.
        """
        e1 = E(eid='e1', procs={'P'}, clock={'P': 1}, props=set())
        e2 = E(eid='e2', procs={'P'}, clock={'P': 2}, props=set())
        e3 = E(eid='e3', procs={'P'}, clock={'P': 3}, props=set())
        assert e1 < e2
        assert e2 < e3
        assert e1 < e3
        assert not (e2 < e1)
        assert e3 > e1
        assert e2 >= e1

    def test_05_string_representation_contains_vc_info(self):
        """
        Tests that the string representation of an event includes its
        process, eid, and vector clock information.
        """
        e = E(eid='evtX', procs={'P'}, clock={'P': 4}, props={'x'})
        s = str(e)
        assert 'evtX' in s
        assert 'P' in s
        assert '[P:4]' in s  # Based on current Event.__str__ format "eid@procs:vc"

    def test_06_has_with_no_props_on_event(self):
        """
        Tests `has()` on an event that carries no propositions.
        It should always return `False`.
        """
        e = E(eid='empty_props', procs={'P'}, clock={'P': 1}, props=set())
        assert e.has('a') is False
        assert e.has('') is False  # Check empty string prop

    def test_07_equality_different_eids_same_content(self):
        """
        Tests that events with different eids but otherwise identical content are not equal.
        """
        e1 = E(eid='ev_one', procs={'P'}, clock={'P': 1}, props={'p'})
        e2 = E(eid='ev_two', procs={'P'}, clock={'P': 1}, props={'p'})
        assert e1 != e2

    def test_08_comparison_leq_reflexive(self):
        """
        Tests that an event is less than or equal to itself (reflexivity of <=).
        """
        e1 = E(eid='e1', procs={'P'}, clock={'P': 1}, props={'a'})
        assert e1 <= e1
        assert e1 >= e1

    def test_09_comparison_strict_inequality(self):
        """
        Tests that if e1 < e2, then e2 is not < e1.
        """
        e1 = E(eid='e1', procs={'P'}, clock={'P': 1}, props=set())
        e2 = E(eid='e2', procs={'P'}, clock={'P': 2}, props=set())
        assert e1 < e2
        assert not (e2 < e1)

    def test_10_event_with_multiple_props_has_all(self):
        """
        Tests `has()` for multiple propositions on a single event.
        """
        e = E(eid='multi', procs={'P'}, clock={'P': 1}, props={'a', 'b', 'c'})
        assert e.has('a') is True
        assert e.has('b') is True
        assert e.has('c') is True
        assert e.has('d') is False

    def test_11_event_with_empty_process_set_creation(self):
        """
        Tests creation of an event associated with an empty set of processes.
        This might be a conceptual event or an edge case.
        """
        # The Event dataclass requires frozenset for processes.
        # An empty frozenset is valid.
        e = E(eid='no_proc_event', procs=set(), clock={}, props={'special'})
        assert e.eid == 'no_proc_event'
        assert len(e.processes) == 0
        assert e.has('special')

    def test_12_event_vc_with_multiple_processes_single_owner(self):
        """
        Tests an event owned by 'P' but its VC reflects knowledge of 'Q'.
        This is valid, e.g., P received a message from Q.
        """
        e = E(eid='p_knows_q', procs={'P'}, clock={'P': 5, 'Q': 3}, props={'data'})
        assert e.vc.clock == {'P': 5, 'Q': 3}
        assert str(e) == "p_knows_q@P:[P:5, Q:3]"

    def test_13_event_comparison_not_equal_to_other_types(self):
        """
        Tests that an Event is not equal to objects of other types.
        """
        e = E(eid='e1', procs={'P'}, clock={'P': 1}, props={'a'})
        assert e != "Event P1"
        assert e != None
        assert e != {'eid': 'e1'}

    def test_14_event_with_numeric_props(self):
        """
        Tests `has()` with proposition names that look like numbers.
        """
        e = E(eid='num_props', procs={'P'}, clock={'P': 1}, props={'123', 'prop456'})
        assert e.has('123')
        assert e.has('prop456')
        assert not e.has('789')

    def test_15_event_hash_for_different_prop_order_in_set(self):
        """
        Tests that hash is consistent even if props set is defined in different order.
        """
        e1 = E(eid='e1', procs={'P'}, clock={'P': 1}, props={'a', 'b'})
        e2 = E(eid='e1', procs={'P'}, clock={'P': 1}, props={'b', 'a'})
        assert hash(e1) == hash(e2)
        assert e1 == e2

    # --- "Complex" Tests (Multi-Owner, Intricate VCs, Concurrency) ---

    def test_16_multi_owner_event_creation_and_has(self):
        """
        Tests creation of a multi-owner event and `has()` method.
        Event 'joint1' on {P,Q} with props 'sync', 'ack'.
        """
        e = E(eid='joint1', procs={'P', 'Q'}, clock={'P': 1, 'Q': 1}, props={'sync', 'ack'})
        assert e.has('sync')
        assert e.has('ack')
        assert not e.has('nack')
        assert e.processes == frozenset({'P', 'Q'})

    def test_17_multi_owner_event_equality_and_hash(self):
        """
        Tests equality and hash for identical multi-owner events.
        """
        e1 = E(eid='j_ev', procs={'A', 'B'}, clock={'A': 2, 'B': 3}, props={'shared'})
        e2 = E(eid='j_ev', procs={'A', 'B'}, clock={'A': 2, 'B': 3}, props={'shared'})
        e3_diff_procs = E(eid='j_ev', procs={'A', 'C'}, clock={'A': 2, 'C': 3}, props={'shared'})

        assert e1 == e2
        assert hash(e1) == hash(e2)
        assert e1 != e3_diff_procs

    def test_18_multi_owner_events_concurrent(self):
        """
        Tests concurrency between two distinct multi-owner events.
        ev_pq @ P:1,Q:1 and ev_rs @ R:1,S:1 are concurrent.
        """
        ev_pq = E(eid='ev_pq', procs={'P', 'Q'}, clock={'P': 1, 'Q': 1}, props=set())
        ev_rs = E(eid='ev_rs', procs={'R', 'S'}, clock={'R': 1, 'S': 1}, props=set())
        assert ev_pq.concurrent(ev_rs)

    def test_19_multi_owner_event_happens_before_another(self):
        """
        Tests happens-before for multi-owner events.
        ev1 @ P:1,Q:1. ev2 @ P:2,Q:2 (ev2 depends on ev1 for both P and Q).
        """
        ev1 = E(eid='ev1', procs={'P', 'Q'}, clock={'P': 1, 'Q': 1}, props=set())
        ev2 = E(eid='ev2', procs={'P', 'Q'}, clock={'P': 2, 'Q': 2}, props=set())  # Assumes ev2 saw ev1
        assert ev1 < ev2
        assert not ev2.concurrent(ev1)

    def test_20_multi_owner_event_str_representation(self):
        """
        Tests string representation of a multi-owner event.
        """
        e = E(eid='sync_ab', procs={'A', 'B'}, clock={'A': 3, 'B': 3, 'C': 1}, props={'done'})
        s = str(e)
        assert 'sync_ab' in s
        assert 'A,B' in s or 'B,A' in s  # Order of procs in string might vary
        assert '[A:3, B:3, C:1]' in s  # Assuming VC string sorts by key

    def test_21_multi_owner_one_proc_ts_zero(self):
        """
        Tests a multi-owner event where one process's timestamp in its VC is 0.
        This could mean it's the first event for that process in this causal path.
        """
        e = E(eid='start_sync', procs={'X', 'Y'}, clock={'X': 1, 'Y': 0}, props={'init'})
        assert e.vc.clock == {'X': 1, 'Y': 0}

    def test_22_multi_owner_vcs_diff_proc_sets_comparable_hb(self):
        """
        Tests comparison of multi-owner events whose VCs have different process sets,
        but one still happens before the other.
        ev1 @ P:1,Q:1. ev2 @ P:2,Q:2,R:1 (ev2 saw ev1 and also involved R).
        """
        ev1 = E(eid='ev1', procs={'P', 'Q'}, clock={'P': 1, 'Q': 1}, props=set())
        ev2 = E(eid='ev2', procs={'P', 'Q', 'R'}, clock={'P': 2, 'Q': 2, 'R': 1}, props=set())
        assert ev1 < ev2

    def test_23_multi_owner_vcs_diff_proc_sets_concurrent(self):
        """
        Tests comparison of multi-owner events whose VCs have different process sets
        and are concurrent.
        ev_pq @ P:1,Q:2. ev_pr @ P:2,R:1.
        """
        ev_pq = E(eid='ev_pq', procs={'P', 'Q'}, clock={'P': 1, 'Q': 2}, props=set())
        ev_pr = E(eid='ev_pr', procs={'P', 'R'}, clock={'P': 2, 'R': 1}, props=set())
        assert ev_pq.concurrent(ev_pr)

    def test_24_multi_owner_compared_to_single_owner_hb(self):
        """
        Tests comparison between a multi-owner and a single-owner event.
        single_p1 @ P:1. joint_p2q1 @ P:2,Q:1 (joint saw single_p1).
        """
        single_p1 = E(eid='s_p1', procs={'P'}, clock={'P': 1}, props=set())
        joint_p2q1 = E(eid='j_p2q1', procs={'P', 'Q'}, clock={'P': 2, 'Q': 1}, props=set())
        assert single_p1 < joint_p2q1

    def test_25_multi_owner_compared_to_single_owner_concurrent(self):
        """
        Tests concurrency between a multi-owner and a single-owner event.
        single_p1 @ P:1. joint_q1r1 @ Q:1,R:1.
        """
        single_p1 = E(eid='s_p1', procs={'P'}, clock={'P': 1}, props=set())
        joint_q1r1 = E(eid='j_q1r1', procs={'Q', 'R'}, clock={'Q': 1, 'R': 1}, props=set())
        assert single_p1.concurrent(joint_q1r1)

    def test_26_complex_vc_comparison_concurrent(self):
        """
        Tests concurrency with more complex vector clocks.
        ev1 @ P:3,Q:2,R:1. ev2 @ P:2,Q:3,S:1.
        """
        ev1 = E(eid='ev1', procs={'P', 'Q', 'R'}, clock={'P': 3, 'Q': 2, 'R': 1}, props=set())
        ev2 = E(eid='ev2', procs={'P', 'Q', 'S'}, clock={'P': 2, 'Q': 3, 'S': 1}, props=set())
        assert ev1.concurrent(ev2)

    def test_27_event_as_join_of_two_others(self):
        """
        Conceptual test: evJ's VC is the join of evA and evB's VCs,
        and evJ is causally after both.
        evA @ P:1. evB @ Q:1. evJ @ P:1,Q:1 (but its own timestamp for P or Q would be higher).
        Let evJ be a sync event on P,Q after they both did something.
        """
        ev_p_local = E(eid='p_local', procs={'P'}, clock={'P': 1}, props=set())
        ev_q_local = E(eid='q_local', procs={'Q'}, clock={'Q': 1}, props=set())

        # Event ev_pq_sync occurs on P and Q, after their local events.
        # Its clock reflects that it "knows" about P:1 and Q:1.
        # And it increments the clocks for P and Q for its own occurrence.
        vc_for_sync = ev_p_local.vc.join(ev_q_local.vc).clock
        # Increment for the sync event itself on P and Q
        vc_for_sync['P'] = vc_for_sync.get('P', 0) + 1  # Becomes P:2
        vc_for_sync['Q'] = vc_for_sync.get('Q', 0) + 1  # Becomes Q:2

        ev_pq_sync = E(eid='pq_sync', procs={'P', 'Q'}, clock=vc_for_sync, props={'synced'})

        assert ev_p_local < ev_pq_sync
        assert ev_q_local < ev_pq_sync
        assert str(ev_pq_sync) == "pq_sync@P,Q:[P:2, Q:2]" or str(ev_pq_sync) == "pq_sync@Q,P:[P:2, Q:2]"
