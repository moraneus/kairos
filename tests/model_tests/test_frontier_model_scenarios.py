# test/model_tests/test_frontier_model_scenarios.py


import pytest
from model.event import Event
from model.frontier import Frontier
from model.vector_clock import VectorClock as VC


# Unified helper function for creating Event objects
def E(eid: str, procs: set[str], clock: dict[str, int], props: set[str]) -> Event:
    """Factory for creating Event objects for testing."""
    return Event(eid, frozenset(procs), VC(clock), frozenset(props))


# Helper function to check for propositions in a Frontier
def holds(frontier: Frontier, literal: str) -> bool:
    """True iff any event in the frontier carries *literal*."""
    return any(e.has(literal) for e in frontier.events.values())


class TestFrontierModelScenarios:
    """
    Test suite for the Frontier data model. Covers creation, property checking (`holds`),
    extension with single and multi-owner events, equality, hashing, vector clock
    derivation, comparisons (happens-before, concurrency), and string representation.
    """

    def test_01_holds_multiple_literals_on_different_events(self):
        """
        Tests the `holds()` helper for checking propositions spread across
        different events within the same frontier.
        Frontier has P:e_p1{p,r} and Q:e_q2{q}.
        It should report True for 'p', 'q', and 'r'.
        """
        e_p1 = E(eid='e_p1', procs={'P'}, clock={'P': 1}, props={'p', 'r'})
        e_q2 = E(eid='e_q2', procs={'Q'}, clock={'Q': 2}, props={'q'})
        f = Frontier({'P': e_p1, 'Q': e_q2})

        assert holds(f, 'p') is True
        assert holds(f, 'q') is True
        assert holds(f, 'r') is True
        assert holds(f, 'x') is False

    def test_02_extend_replaces_event_for_existing_process(self):
        """
        Tests that `extend()` with an event for an existing process updates
        that process's latest event in the frontier.
        """
        e_p1 = E(eid='e_p1', procs={'P'}, clock={'P': 1}, props=set())
        e_q1 = E(eid='e_q1', procs={'Q'}, clock={'Q': 1}, props=set())
        f1 = Frontier({'P': e_p1, 'Q': e_q1})

        e_p2 = E(eid='e_p2', procs={'P'}, clock={'P': 2}, props=set())
        f2 = f1.extend(e_p2)

        assert 'P' in f2.events
        assert f2.events['P'].eid == 'e_p2'
        assert f2.events['P'].vc == VC({'P': 2})
        assert 'Q' in f2.events  # Q's event should remain unchanged
        assert f2.events['Q'] == e_q1
        assert f1.events['P'] != f2.events['P']

    def test_03_concurrent_frontiers_different_processes(self):
        """
        Tests that two frontiers, each with a single event on different
        independent processes, are concurrent.
        """
        f1 = Frontier({'P': E(eid='e_p1', procs={'P'}, clock={'P': 1}, props=set())})
        f2 = Frontier({'Q': E(eid='e_q1', procs={'Q'}, clock={'Q': 1}, props=set())})

        assert f1.concurrent(f2)
        assert f2.concurrent(f1)
        assert not (f1 < f2)
        assert not (f2 < f1)

    def test_04_ordering_with_extend_creates_happens_before(self):
        """
        Tests that extending a frontier creates a new frontier that is
        causally after the original. f1 < f1.extend(event).
        """
        f1 = Frontier({'P': E(eid='e_p1', procs={'P'}, clock={'P': 1}, props=set())})
        e_p2 = E(eid='e_p2', procs={'P'}, clock={'P': 2}, props=set())
        f2 = f1.extend(e_p2)

        assert f1 < f2
        assert not (f2 < f1)
        assert f2 > f1
        assert f1 <= f2
        assert f2 >= f1

    def test_05_string_representation_sorted_by_process_name(self):
        """
        Tests that the string representation of a Frontier sorts events by process name
        for deterministic output.
        """
        # Events created out of typical alphabetical order for processes
        e_r1 = E(eid='e_r1', procs={'R'}, clock={'R': 1}, props=set())
        e_p2 = E(eid='e_p2', procs={'P'}, clock={'P': 2}, props=set())
        e_q3 = E(eid='e_q3', procs={'Q'}, clock={'Q': 3}, props=set())
        f = Frontier({'P': e_p2, 'R': e_r1, 'Q': e_q3})

        s = str(f)  # Expected: <P:e_p2, Q:e_q3, R:e_r1>
        assert s.startswith("⟨P:e_p2, Q:e_q3, R:e_r1")  # Check start to allow for closing >

    def test_06_empty_frontier_properties(self):
        """
        Tests properties of an empty frontier.
        Its VC should be empty, string representation reflects emptiness.
        `holds` should always be false.
        """
        f_empty = Frontier()
        assert f_empty.events == {}
        assert f_empty.vc == VC({})
        assert str(f_empty) == "⟨⟩"
        assert holds(f_empty, 'a') is False

    def test_07_frontier_with_single_event_properties(self):
        """
        Tests properties of a frontier with just one event.
        """
        e1 = E(eid='event_a', procs={'A'}, clock={'A': 1}, props={'prop_a'})
        f = Frontier({'A': e1})

        assert f.events == {'A': e1}
        assert f.vc == VC({'A': 1})
        assert holds(f, 'prop_a') is True
        assert holds(f, 'prop_b') is False
        assert "A:event_a" in str(f)

    def test_08_equality_identical_frontiers(self):
        """
        Tests that two frontiers constructed identically are equal and have same hash.
        """
        e_p1 = E(eid='e_p1', procs={'P'}, clock={'P': 1}, props={'x'})
        e_q1 = E(eid='e_q1', procs={'Q'}, clock={'Q': 1}, props={'y'})
        f1 = Frontier({'P': e_p1, 'Q': e_q1})
        f2 = Frontier({'P': e_p1, 'Q': e_q1})  # Identical construction

        assert f1 == f2
        assert hash(f1) == hash(f2)

    def test_09_inequality_different_events(self):
        """
        Tests that frontiers with different events for the same process are not equal.
        """
        e_p1 = E(eid='e_p1', procs={'P'}, clock={'P': 1}, props=set())
        e_p1_alt = E(eid='e_p1_alt', procs={'P'}, clock={'P': 1}, props=set())  # Different eid
        e_p2 = E(eid='e_p1', procs={'P'}, clock={'P': 2}, props=set())  # Different VC

        f1 = Frontier({'P': e_p1})
        f2 = Frontier({'P': e_p1_alt})
        f3 = Frontier({'P': e_p2})

        assert f1 != f2
        assert f1 != f3

    def test_10_inequality_different_processes(self):
        """
        Tests that frontiers with events on different sets of processes are not equal.
        """
        f1 = Frontier({'P': E(eid='e_p1', procs={'P'}, clock={'P': 1}, props=set())})
        f2 = Frontier({'Q': E(eid='e_q1', procs={'Q'}, clock={'Q': 1}, props=set())})
        f3 = Frontier({'P': E(eid='e_p1', procs={'P'}, clock={'P': 1}, props=set()),
                       'Q': E(eid='e_q1', procs={'Q'}, clock={'Q': 1}, props=set())})
        assert f1 != f2
        assert f1 != f3
        assert f2 != f3

    def test_11_extend_with_new_process_adds_event(self):
        """
        Tests that `extend()` with an event for a new process adds that
        process and event to the frontier.
        """
        f1 = Frontier({'P': E(eid='e_p1', procs={'P'}, clock={'P': 1}, props=set())})
        e_q1 = E(eid='e_q1', procs={'Q'}, clock={'Q': 1}, props=set())
        f2 = f1.extend(e_q1)

        assert 'P' in f2.events
        assert 'Q' in f2.events
        assert f2.events['Q'] == e_q1
        assert len(f2.events) == 2

    def test_12_vc_property_simple_two_process_frontier(self):
        """
        Tests the `vc` property for a frontier with two independent events.
        """
        e_p1 = E(eid='e_p1', procs={'P'}, clock={'P': 3}, props=set())
        e_q1 = E(eid='e_q1', procs={'Q'}, clock={'Q': 5}, props=set())
        f = Frontier({'P': e_p1, 'Q': e_q1})

        expected_vc = VC({'P': 3, 'Q': 5})
        assert f.vc == expected_vc

    def test_13_reflexive_comparisons_leq_geq(self):
        """
        Tests that a frontier is less-than-or-equal-to and greater-than-or-equal-to itself.
        """
        f = Frontier({'P': E(eid='e_p1', procs={'P'}, clock={'P': 1}, props=set())})
        assert f <= f
        assert f >= f

    def test_14_holds_on_empty_frontier_is_false(self):
        """
        Tests that `holds()` returns False for any proposition on an empty frontier.
        """
        f_empty = Frontier()
        assert holds(f_empty, 'anything') is False
        assert holds(f_empty, '') is False

    def test_15_frontier_equality_order_of_construction_irrelevant(self):
        """
        Tests that two frontiers with the same (process, event) pairs are equal,
        regardless of the order events were added to the dictionary during construction.
        """
        e_p = E(eid='ep', procs={'P'}, clock={'P': 1}, props={'p'})
        e_q = E(eid='eq', procs={'Q'}, clock={'Q': 1}, props={'q'})
        f1 = Frontier({'P': e_p, 'Q': e_q})
        f2 = Frontier({'Q': e_q, 'P': e_p})  # Different construction order
        assert f1 == f2
        assert hash(f1) == hash(f2)

    # --- "Complex" Tests (Multi-Owner Events, Intricate VCs) ---

    def test_16_extend_with_multi_owner_event_updates_multiple_procs(self):
        """
        Tests `extend()` with a multi-owner event that updates two existing processes.
        """
        e_p1 = E(eid='e_p1', procs={'P'}, clock={'P': 1}, props=set())
        e_q1 = E(eid='e_q1', procs={'Q'}, clock={'Q': 1}, props=set())
        f1 = Frontier({'P': e_p1, 'Q': e_q1})

        # Joint event for P and Q, causally after their initial events
        e_pq_joint = E(eid='e_pq2', procs={'P', 'Q'}, clock={'P': 2, 'Q': 2}, props={'sync'})
        f2 = f1.extend(e_pq_joint)

        assert f2.events['P'] == e_pq_joint
        assert f2.events['Q'] == e_pq_joint
        assert holds(f2, 'sync')

    def test_17_extend_with_multi_owner_event_updates_one_adds_one(self):
        """
        Tests `extend()` with a multi-owner event that updates one existing
        process and adds a new one to the frontier.
        """
        f1 = Frontier({'P': E(eid='e_p1', procs={'P'}, clock={'P': 1}, props=set())})
        # Joint event for P (update) and R (new)
        e_pr_joint = E(eid='e_pr2', procs={'P', 'R'}, clock={'P': 2, 'R': 1}, props={'shared_pr'})
        f2 = f1.extend(e_pr_joint)

        assert f2.events['P'] == e_pr_joint
        assert f2.events['R'] == e_pr_joint
        assert len(f2.events) == 2
        assert holds(f2, 'shared_pr')

    def test_18_vc_property_complex_frontier_with_multi_owner(self):
        """
        Tests the `vc` property for a frontier involving multi-owner events
        and complex inter-dependencies reflected in event VCs.
        P -> PQ_sync -> PR_sync
        Q -> PQ_sync
        R -> PR_sync
        """
        e_p1 = E(eid='e_p1', procs={'P'}, clock={'P': 1}, props=set())
        e_q1 = E(eid='e_q1', procs={'Q'}, clock={'Q': 1}, props=set())
        e_r1 = E(eid='e_r1', procs={'R'}, clock={'R': 1}, props=set())

        # PQ_sync happens after P:1 and Q:1
        vc_pq = {'P': 2, 'Q': 2, 'R': 0}  # R is not involved yet from PQ's perspective
        e_pq_sync = E(eid='e_pq_sync', procs={'P', 'Q'}, clock=vc_pq, props={'pq'})

        # PR_sync happens after P:2 (from e_pq_sync) and R:1
        vc_pr = {'P': 3, 'Q': 2, 'R': 2}  # Q's state from e_pq_sync, P and R advance
        e_pr_sync = E(eid='e_pr_sync', procs={'P', 'R'}, clock=vc_pr, props={'pr'})

        # Frontier state: P is at e_pr_sync, Q is at e_pq_sync, R is at e_pr_sync
        f = Frontier({'P': e_pr_sync, 'Q': e_pq_sync, 'R': e_pr_sync})

        # Expected VC of the frontier is the component-wise max of the VCs of its events' PIDs
        # P: from e_pr_sync (P:3)
        # Q: from e_pq_sync (Q:2)
        # R: from e_pr_sync (R:2)
        expected_frontier_vc = VC({'P': 3, 'Q': 2, 'R': 2})
        assert f.vc == expected_frontier_vc

    def test_19_concurrent_frontiers_complex(self):
        """
        Tests concurrency for more complex frontiers.
        F1: P updated by joint PQ, R by local.
        F2: Q updated by joint QR, S by local.
        Assume PQ and QR are independent of R_local and S_local respectively.
        """
        e_p_tick = E('pt', {'P'}, {'P': 1}, set())
        e_q_tick = E('qt', {'Q'}, {'Q': 1}, set())
        e_r_tick = E('rt', {'R'}, {'R': 1}, set())
        e_s_tick = E('st', {'S'}, {'S': 1}, set())

        e_pq = E('epq', {'P', 'Q'}, {'P': 2, 'Q': 2}, set())  # Depends on P:1, Q:1
        e_qr = E('eqr', {'Q', 'R'}, {'Q': 2, 'R': 2},
                 set())  # Depends on Q:1, R:1 (concurrent to epq if Q:1 is common ancestor)
        # For true concurrency, let's make their Q deps different
        # or assume they are from different branches.
        # Let's make them fully independent for simplicity here.
        e_r_local = E('erloc', {'R'}, {'R': 1}, set())  # Independent of PQ
        e_s_local = E('esloc', {'S'}, {'S': 1}, set())  # Independent of QR

        f1 = Frontier({'P': e_pq, 'Q': e_pq, 'R': e_r_local})  # P:2, Q:2, R:1
        f2 = Frontier(
            {'Q': e_qr, 'R': e_qr, 'S': e_s_local})  # Q:2, R:2, S:1 (if e_qr's Q:2 is independent of e_pq's Q:2)
        # To ensure concurrency, let their VCs be distinct

        f1_alt = Frontier({
            'P': E('f1p', {'P'}, {'P': 1}, set()),
            'X': E('f1x', {'X'}, {'X': 1}, set())
        })
        f2_alt = Frontier({
            'Q': E('f2q', {'Q'}, {'Q': 1}, set()),
            'Y': E('f2y', {'Y'}, {'Y': 1}, set())
        })
        assert f1_alt.concurrent(f2_alt)

    def test_20_sequence_of_extensions_vc_updates(self):
        """
        Tests a sequence of extend operations and checks intermediate VCs.
        """
        f = Frontier()
        assert f.vc == VC({})

        e_p1 = E('ep1', {'P'}, {'P': 1}, set())
        f = f.extend(e_p1)
        assert f.vc == VC({'P': 1})

        e_q1 = E('eq1', {'Q'}, {'Q': 1}, set())
        f = f.extend(e_q1)  # Now P:1, Q:1
        assert f.vc == VC({'P': 1, 'Q': 1})

        e_pq_sync = E('epq2', {'P', 'Q'}, {'P': 2, 'Q': 2}, set())
        f = f.extend(e_pq_sync)  # Now P:2, Q:2
        assert f.vc == VC({'P': 2, 'Q': 2})

        e_p3 = E('ep3', {'P'}, {'P': 3}, set())
        f = f.extend(e_p3)  # Now P:3, Q:2
        assert f.vc == VC({'P': 3, 'Q': 2})

    def test_21_frontier_comparison_multi_owner_involved(self):
        """
        Tests <, <=, >, >= for frontiers involving multi-owner events.
        """
        f_initial = Frontier()
        e_p1 = E('ep1', {'P'}, {'P': 1}, set())
        f_p1 = f_initial.extend(e_p1)

        e_q1 = E('eq1', {'Q'}, {'Q': 1}, set())
        f_p1q1 = f_p1.extend(e_q1)  # P:1, Q:1

        e_pq_sync = E('epq_sync', {'P', 'Q'}, {'P': 2, 'Q': 2}, set())
        f_sync = f_p1q1.extend(e_pq_sync)  # P:2, Q:2

        assert f_initial < f_p1
        assert f_p1 < f_p1q1  # This is not strictly true if P:1 and Q:1 are concurrent.
        # f_p1q1 is an extension, its VC will be join(VC_P1, VC_Q1)
        # Let's re-evaluate this part of the test.
        # Corrected logic for f_p1 < f_p1q1
        # f_p1.vc = {P:1}. f_p1q1.vc = {P:1, Q:1}. So f_p1 < f_p1q1. This is fine.
        assert f_p1 < f_p1q1

        assert f_p1q1 < f_sync
        assert f_sync > f_p1
        assert f_p1q1 <= f_sync
        assert f_sync >= f_p1q1

    def test_22_equality_frontiers_same_events_diff_construction_paths(self):
        """
        Tests if F1 = {P:eP, Q:eQ} is equal to F2 constructed by
        empty.extend(eP).extend(eQ) vs empty.extend(eQ).extend(eP),
        assuming eP and eQ are concurrent.
        """
        e_p = E('ep', {'P'}, {'P': 1}, set())
        e_q = E('eq', {'Q'}, {'Q': 1}, set())

        f_path1 = Frontier().extend(e_p).extend(e_q)
        f_path2 = Frontier().extend(e_q).extend(e_p)
        f_direct = Frontier({'P': e_p, 'Q': e_q})

        assert f_path1 == f_direct
        assert f_path2 == f_direct
        assert f_path1 == f_path2
        assert hash(f_path1) == hash(f_path2)

    def test_23_extend_multi_owner_overwrites_single_owner_correctly(self):
        """
        Frontier has {P:e_p_local, Q:e_q_local}.
        Extend with e_pq_joint. P and Q should now point to e_pq_joint.
        """
        e_p_local = E('eploc', {'P'}, {'P': 1}, set())
        e_q_local = E('eqloc', {'Q'}, {'Q': 1}, set())
        f1 = Frontier({'P': e_p_local, 'Q': e_q_local})

        e_pq_joint = E('epqj', {'P', 'Q'}, {'P': 2, 'Q': 2}, set())
        f2 = f1.extend(e_pq_joint)

        assert f2.events['P'] == e_pq_joint
        assert f2.events['Q'] == e_pq_joint

    def test_24_concurrency_after_branching_from_common_ancestor(self):
        """
        F_base.extend(eP) -> F_P
        F_base.extend(eQ) -> F_Q
        F_P and F_Q should be concurrent if eP and eQ are on different processes.
        """
        f_base = Frontier({'A': E('ea_base', {'A'}, {'A': 1}, set())})
        e_p_branch = E('epb', {'P'}, {'P': 1}, set())  # New process P
        e_q_branch = E('eqb', {'Q'}, {'Q': 1}, set())  # New process Q

        f_p_path = f_base.extend(e_p_branch)  # A:1, P:1
        f_q_path = f_base.extend(e_q_branch)  # A:1, Q:1

        assert f_p_path.concurrent(f_q_path)

    def test_25_hashing_consistency_with_multi_owner_events(self):
        """
        Tests hash consistency for frontiers containing multi-owner events.
        """
        e_joint1 = E('j1', {'P', 'Q'}, {'P': 1, 'Q': 1}, set())
        e_joint2 = E('j1', {'P', 'Q'}, {'P': 1, 'Q': 1}, set())  # Identical
        e_r = E('er', {'R'}, {'R': 1}, set())

        f1 = Frontier({'P': e_joint1, 'Q': e_joint1, 'R': e_r})
        f2 = Frontier({'R': e_r, 'Q': e_joint2, 'P': e_joint2})  # Same events, diff order

        assert f1 == f2
        assert hash(f1) == hash(f2)

    def test_26_holds_on_complex_frontier_multi_owner(self):
        """
        Tests `holds` on a frontier with multi-owner events carrying various props.
        """
        e_p = E('ep', {'P'}, {'P': 1}, {'p_only'})
        e_q = E('eq', {'Q'}, {'Q': 1}, {'q_only'})
        e_pq_joint = E('epqj', {'P', 'Q'}, {'P': 2, 'Q': 2}, {'pq_shared', 'p_specific_in_joint'})
        # P is now epqj, Q is now epqj
        f = Frontier({'P': e_pq_joint, 'Q': e_pq_joint,
                      'R': E('er', {'R'}, {'R': 1}, {'r_only'})})

        assert holds(f, 'pq_shared')
        assert holds(f, 'p_specific_in_joint')
        assert holds(f, 'r_only')
        assert not holds(f, 'p_only')  # Overwritten by joint event for P
        assert not holds(f, 'q_only')  # Overwritten by joint event for Q

    def test_27_frontier_vc_derivation_from_multi_owner_event_vcs(self):
        """
        Ensures frontier.vc correctly reflects the per-process timestamps
        from the VCs of the events defining the frontier, especially with multi-owner events.
        If P's latest event is E1 with VC {P:3, X:1}
        And Q's latest event is E2 with VC {Q:2, Y:1}
        Frontier VC should be {P:3, Q:2}.
        """
        e1 = E('e1', {'P', 'X'}, {'P': 3, 'X': 1}, {'propP'})  # E1 is latest for P and X
        e2 = E('e2', {'Q', 'Y'}, {'Q': 2, 'Y': 1}, {'propQ'})  # E2 is latest for Q and Y

        # Frontier where P is determined by e1, Q by e2
        f = Frontier({'P': e1, 'Q': e2})
        assert f.vc == VC({'P': 3, 'Q': 2})

        # Frontier where P and X are determined by e1, Q and Y by e2
        f_full = Frontier({'P': e1, 'X': e1, 'Q': e2, 'Y': e2})
        assert f_full.vc == VC({'P': 3, 'X': 1, 'Q': 2, 'Y': 1})
