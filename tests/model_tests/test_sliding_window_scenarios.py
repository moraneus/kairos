# test/model_tests/test_window_model_scenarios.py


import pytest
from model.event import Event
from model.frontier import Frontier
from model.vector_clock import VectorClock as VC
from model.window import SlidingFrontierWindow


# Unified helper function for creating Event objects
def E(eid: str, procs: set[str], clock: dict[str, int], props: set[str]) -> Event:
    """Factory for creating Event objects for testing."""
    return Event(eid, frozenset(procs), VC(clock), frozenset(props))


# Helper function to check for propositions in a Frontier
# Defined at module level for accessibility by all test methods
def holds(frontier: Frontier, literal: str) -> bool:
    """True iff any event in the frontier carries *literal*."""
    if not frontier or not frontier.events:  # Handle empty or uninitialized frontier
        return False
    return any(e.has(literal) for e in frontier.events.values())


class TestSlidingFrontierWindowScenarios:
    """
    Test suite for the SlidingFrontierWindow data model.
    Covers initialization, extend, commit_and_prune_candidates, prune
    (de-duplication, maximality, size cap, Rs-pruning),
    latest, clear, len, and bool, with single and multi-owner events.
    Assumes prune always filters to maximals before applying max_size.
    """

    def test_01_window_respects_max_size_with_concurrent_events(self):
        """
        Insert five concurrent events. The window's `extend` and `prune`
        should result in a single maximal frontier containing all five events.
        max_size=3 is not the limiting factor here maximality is.
        """
        win = SlidingFrontierWindow(max_size=3)
        events_inserted_details = []
        all_procs = "ABCDE"

        for i, p_char in enumerate(all_procs):
            event = E(f'e{p_char}1', {p_char}, {p_char: 1}, set())
            events_inserted_details.append({'proc': p_char, 'event_obj': event})
            candidates = win.extend(event)
            win.commit_and_prune_candidates(candidates)

        assert len(win) == 1
        latest_f = win.latest
        assert latest_f is not None
        assert len(latest_f.events) == len(all_procs)
        for detail in events_inserted_details:
            assert latest_f.events[detail['proc']] == detail['event_obj']

    def test_02_extend_with_later_event_on_same_process_keeps_maximal(self):
        """
        Two events on the SAME process (happens-before ordered).
        The window should only keep the frontier corresponding to the later event.
        """
        win = SlidingFrontierWindow(max_size=5)
        event_p1 = E('p1', {'P'}, {'P': 1}, set())
        candidates_p1 = win.extend(event_p1)
        win.commit_and_prune_candidates(candidates_p1)

        event_p2 = E('p2', {'P'}, {'P': 2}, set())
        candidates_p2 = win.extend(event_p2)
        win.commit_and_prune_candidates(candidates_p2)

        assert len(win) == 1
        assert win.latest is not None
        assert win.latest.events['P'].vc.clock["P"] == 2
        assert win.latest.events['P'].eid == 'p2'

    def test_03_latest_is_member_after_mixed_extensions(self):
        """
        Mix happens-before and concurrent event extensions `latest` must
        always be one of the stored (maximal) frontiers.
        """
        win = SlidingFrontierWindow(max_size=5)

        cand1 = win.extend(E('q1', {'Q'}, {'Q': 1}, set()))
        win.commit_and_prune_candidates(cand1)

        q2_event = E('q2', {'Q'}, {'Q': 2}, set())
        cand2 = win.extend(q2_event)
        win.commit_and_prune_candidates(cand2)

        r1_event = E('r1', {'R'}, {'R': 1}, set())
        cand3 = win.extend(r1_event)
        win.commit_and_prune_candidates(cand3)

        assert win.latest is not None
        assert win.latest in win.frontiers
        latest_events_eids = {ev.eid for ev in win.latest.events.values()}
        assert 'q2' in latest_events_eids
        assert 'r1' in latest_events_eids

    def test_04_bool_and_clear_helpers(self):
        """Tests boolean context (__bool__) and clear() method."""
        win = SlidingFrontierWindow()
        assert not win

        cand = win.extend(E('p1', {'P'}, {'P': 1}, set()))
        win.commit_and_prune_candidates(cand)
        assert win
        assert len(win) == 1

        win.clear()
        assert not win
        assert len(win) == 0

    def test_05_initial_window_is_empty(self):
        """An empty window should have length 0 and no latest frontier."""
        win = SlidingFrontierWindow()
        assert len(win) == 0
        assert win.latest is None
        assert list(win) == []

    def test_06_extend_empty_window_with_one_event(self):
        """Extending an empty window with one event."""
        win = SlidingFrontierWindow()
        event_a1 = E('a1', {'A'}, {'A': 1}, {'propA'})

        candidates = win.extend(event_a1)
        win.commit_and_prune_candidates(candidates)

        assert len(win) == 1
        assert win.latest is not None
        assert win.latest.events['A'] == event_a1
        assert holds(win.latest, 'propA')

    def test_07_extend_with_two_concurrent_events_different_procs(self):
        """Extending with two concurrent events on different processes."""
        win = SlidingFrontierWindow(max_size=5)
        event_p1 = E('p1', {'P'}, {'P': 1}, set())
        event_q1 = E('q1', {'Q'}, {'Q': 1}, set())

        candidates_p = win.extend(event_p1)
        win.commit_and_prune_candidates(candidates_p)

        candidates_q = win.extend(event_q1)
        win.commit_and_prune_candidates(candidates_q)

        assert len(win) == 1
        assert win.latest is not None
        latest_frontier = win.latest
        assert latest_frontier.events['P'] == event_p1
        assert latest_frontier.events['Q'] == event_q1

    def test_08_max_size_respected_with_many_sequential_events_same_proc(self):
        """Max_size should be 1 after many sequential events on the same process."""
        win = SlidingFrontierWindow(max_size=3)
        for i in range(1, 6):
            event = E(f'p{i}', {'P'}, {'P': i}, set())
            candidates = win.extend(event)
            win.commit_and_prune_candidates(candidates)
        assert len(win) == 1
        assert win.latest.events['P'].vc.clock['P'] == 5

    def test_09_max_size_respected_with_many_concurrent_events(self):
        """
        Window with max_size=2. Adding 3 concurrent events.
        Should result in 1 maximal frontier containing all 3.
        """
        win = SlidingFrontierWindow(max_size=2)
        procs = "ABC"
        events = [E(f'{p}1', {p}, {p: 1}, set()) for p in procs]

        for event in events:
            candidates = win.extend(event)
            win.commit_and_prune_candidates(candidates)

        assert len(win) == 1
        latest_f = win.latest
        assert len(latest_f.events) == 3

    def test_10_iteration_order_after_pruning_complex(self):
        """
        Sequence: P1, then Q1 (concurrent), then P2 (dominates P1).
        Expected final maximal: Frontier({P:P2, Q:Q1}).
        """
        win = SlidingFrontierWindow(max_size=2)
        e_p1 = E('p1', {'P'}, {'P': 1}, set())
        e_q1 = E('q1', {'Q'}, {'Q': 1}, set())
        e_p2 = E('p2', {'P'}, {'P': 2}, set())

        cand1 = win.extend(e_p1)
        win.commit_and_prune_candidates(cand1)
        cand2 = win.extend(e_q1)
        win.commit_and_prune_candidates(cand2)
        cand3 = win.extend(e_p2)
        win.commit_and_prune_candidates(cand3)

        final_frontiers = list(win)
        assert len(final_frontiers) == 1
        assert final_frontiers[0].events.get('P') == e_p2
        assert final_frontiers[0].events.get('Q') == e_q1

    def test_11_max_size_one(self):
        """Window with max_size=1 should always contain at most one frontier."""
        win = SlidingFrontierWindow(max_size=1)

        cand = win.extend(E('p1', {'P'}, {'P': 1}, set()))
        win.commit_and_prune_candidates(cand)
        assert len(win) == 1

        cand = win.extend(E('q1', {'Q'}, {'Q': 1}, set()))
        win.commit_and_prune_candidates(cand)
        assert len(win) == 1

        cand = win.extend(E('p2', {'P'}, {'P': 2}, set()))
        win.commit_and_prune_candidates(cand)
        assert len(win) == 1
        assert win.latest.events['P'].vc.clock['P'] == 2
        assert 'Q' in win.latest.events

    def test_12_insert_method_basic(self):
        """
        Test direct insertion of two concurrent frontiers.
        Prune keeps maximals. If max_size allows, both are kept.
        """
        win = SlidingFrontierWindow(max_size=2)
        f1 = Frontier({'A': E('a1', {'A'}, {'A': 1}, set())})
        f2 = Frontier({'B': E('b1', {'B'}, {'B': 1}, set())})

        win.insert(f1)
        assert len(win) == 1

        win.insert(f2)
        # After inserting f2: self.frontiers = [f1, f2]
        # Prune: de-dup -> [f1, f2]. Maximality -> [f1, f2] (concurrent). Size cap (2<=2) -> [f1, f2].
        assert len(win) == 2
        assert f1 in win.frontiers
        assert f2 in win.frontiers

    def test_13_insert_method_triggers_pruning_to_maximal(self):
        """Test `insert` triggers pruning that respects maximality."""
        win = SlidingFrontierWindow(max_size=2)
        f_p1 = Frontier({'P': E('p1', {'P'}, {'P': 1}, set())})
        f_p2 = Frontier({'P': E('p2', {'P'}, {'P': 2}, set())})  # f_p1 < f_p2

        win.insert(f_p1)
        win.insert(f_p2)
        assert len(win) == 1
        assert win.latest == f_p2

    def test_14_insert_method_respects_max_size(self):
        """
        Test `insert` respects max_size after maximality.
        Insert 3 concurrent frontiers into max_size=1 window.
        Should end up with 1 (the last one inserted among maximals).
        """
        win = SlidingFrontierWindow(max_size=1)
        f_p1 = Frontier({'P': E('p1', {'P'}, {'P': 1}, set())})
        f_q1 = Frontier({'Q': E('q1', {'Q'}, {'Q': 1}, set())})
        f_r1 = Frontier({'R': E('r1', {'R'}, {'R': 1}, set())})

        win.insert(f_p1)
        win.insert(f_q1)
        win.insert(f_r1)

        assert len(win) == 1
        assert win.latest == f_r1

    def test_15_extend_with_multi_owner_event(self):
        """Extend with a multi-owner event, check window state."""
        win = SlidingFrontierWindow(max_size=5)
        cand_p1 = win.extend(E('p1', {'P'}, {'P': 1}, set()))
        win.commit_and_prune_candidates(cand_p1)
        cand_q1 = win.extend(E('q1', {'Q'}, {'Q': 1}, set()))
        win.commit_and_prune_candidates(cand_q1)

        e_pq_sync = E('pq_sync', {'P', 'Q'}, {'P': 2, 'Q': 2}, {'sync'})
        cand_sync = win.extend(e_pq_sync)
        win.commit_and_prune_candidates(cand_sync)

        assert len(win) == 1
        latest_f = win.latest
        assert latest_f.events['P'] == e_pq_sync
        assert latest_f.events['Q'] == e_pq_sync
        assert holds(latest_f, 'sync')

    def test_16_diamond_completion_through_extend(self):
        """
        Test if extend logic correctly forms the 'diamond' (s + e1 + e2).
        """
        win = SlidingFrontierWindow(max_size=5)
        s_event = E('s0', {'S'}, {'S': 1}, set())
        e1 = E('e1', {'P'}, {'P': 1}, set())
        e2 = E('e2', {'Q'}, {'Q': 1}, set())

        cand0 = win.extend(s_event)
        win.commit_and_prune_candidates(cand0)
        cand1 = win.extend(e1)
        win.commit_and_prune_candidates(cand1)
        cand2 = win.extend(e2)
        win.commit_and_prune_candidates(cand2)

        assert len(win) == 1
        final_f = win.latest
        assert final_f.events.get('S') == s_event
        assert final_f.events.get('P') == e1
        assert final_f.events.get('Q') == e2

    def test_17_de_duplication_in_prune(self):
        """Ensure prune removes duplicates."""
        win = SlidingFrontierWindow(max_size=5)
        e_p1 = E('p1', {'P'}, {'P': 1}, set())
        f_p1 = Frontier({'P': e_p1})
        f_q1 = Frontier({'Q': E('q1', {'Q'}, {'Q': 1}, set())})

        win.frontiers = [f_p1, f_q1, f_p1, f_p1, f_q1]
        win.prune()

        assert len(win) == 2
        assert win.frontiers.count(f_p1) == 1
        assert win.frontiers.count(f_q1) == 1

    def test_18_maximality_filtering_in_prune(self):
        """Show non-maximal frontiers are pruned."""
        win = SlidingFrontierWindow(max_size=3)
        f_p1 = Frontier({'P': E('p1', {'P'}, {'P': 1}, set())})
        f_p2 = Frontier({'P': E('p2', {'P'}, {'P': 2}, set())})
        f_q1 = Frontier({'Q': E('q1', {'Q'}, {'Q': 1}, set())})

        win.frontiers = [f_p1, f_p2, f_q1, f_p1]
        win.prune()
        assert len(win) == 2
        assert f_p1 not in win.frontiers
        assert f_p2 in win.frontiers
        assert f_q1 in win.frontiers

    def test_19_rs_pruning_active_frontier_removed(self):
        """Activate Rs-pruning, show a frontier is removed when Rs covers all system procs."""
        win = SlidingFrontierWindow(max_size=5)
        win.activate_optimized_pruning({'P', 'Q'})

        # This frontier is just a placeholder event from a different process 'A'
        # Its Rs set will be updated by extend calls.
        f_to_be_pruned_by_rs = Frontier({'A': E('a_placeholder', {'A'}, {'A': 1}, set())})
        win.insert(f_to_be_pruned_by_rs)

        # Simulate outgoing events from f_to_be_pruned_by_rs for P and Q
        # In real scenario, extend(event_on_P) and extend(event_on_Q) would update Rs for f_to_be_pruned_by_rs
        # if f_to_be_pruned_by_rs was a seed for those extensions.
        # For this test, we directly manipulate the Rs map after insertion.
        if f_to_be_pruned_by_rs in win._frontier_outgoing_processes:
            win._frontier_outgoing_processes[f_to_be_pruned_by_rs] = {'P', 'Q'}
        else:  # f_to_be_pruned_by_rs might have been pruned if it was empty and another was inserted
            # Let's re-insert to ensure it's there before we modify its Rs
            win.clear()
            win.activate_optimized_pruning({'P', 'Q'})  # reset
            win.insert(f_to_be_pruned_by_rs)
            if f_to_be_pruned_by_rs in win._frontier_outgoing_processes:
                win._frontier_outgoing_processes[f_to_be_pruned_by_rs] = {'P', 'Q'}
            else:
                pytest.fail("Rs tracking not initialized for inserted frontier via insert for Rs test")

        f_other = Frontier({'X': E('x1', {'X'}, {'X': 1}, set())})
        win.insert(f_other)  # This call to insert will trigger prune

        assert f_to_be_pruned_by_rs not in win.frontiers
        assert f_other in win.frontiers

    def test_20_rs_pruning_active_frontier_not_removed_if_rs_incomplete(self):
        """Activate Rs-pruning, show frontier NOT removed if Rs is incomplete."""
        win = SlidingFrontierWindow(max_size=5)
        win.activate_optimized_pruning({'P', 'Q', 'R'})

        f_pr_partially_covered = Frontier({'B': E('b1', {'B'}, {'B': 1}, set())})
        win.insert(f_pr_partially_covered)
        if f_pr_partially_covered in win._frontier_outgoing_processes:
            win._frontier_outgoing_processes[f_pr_partially_covered] = {'P', 'R'}
        else:
            pytest.fail("Rs tracking not initialized for inserted frontier via insert")

        win.insert(Frontier({'Y': E('y1', {'Y'}, {'Y': 1}, set())}))
        assert f_pr_partially_covered in win.frontiers

    def test_21_interaction_of_all_pruning_rules(self):
        """
        Complex scenario testing de-dup, Rs, maximality, and size cap.
        max_size = 1.
        F1 (Rs complete), F2 (non-maximal < F3), F3 (maximal), F4 (maximal, concurrent F3)
        Expected: F4 (if F4 is "more recent" maximal than F3 after F1,F2 pruned)
        """
        win = SlidingFrontierWindow(max_size=1)
        win.activate_optimized_pruning({'SysP'})

        f1_rs_done = Frontier({'P_holder': E('p1_rs', {'P_holder'}, {'P_holder': 1}, set())})
        f2_non_max = Frontier({'Q_holder': E('q1_nm', {'Q_holder'}, {'Q_holder': 1}, set())})
        f3_maximal = Frontier({'Q_holder': E('q2_m', {'Q_holder'}, {'Q_holder': 2}, set())})
        f4_maximal_other = Frontier({'R_holder': E('r1_mo', {'R_holder'}, {'R_holder': 1}, set())})

        # Manually set initial state for prune to process
        win.frontiers = [f1_rs_done, f2_non_max, f3_maximal, f4_maximal_other, f2_non_max]

        for f_init in [f1_rs_done, f2_non_max, f3_maximal, f4_maximal_other]:
            if f_init.events and f_init not in win._frontier_outgoing_processes:  # Ensure Rs map has keys
                win._frontier_outgoing_processes[f_init] = set()
        if f1_rs_done in win._frontier_outgoing_processes:  # Check before assignment
            win._frontier_outgoing_processes[f1_rs_done] = {'SysP'}

        win.prune()
        assert len(win) == 1
        assert win.latest == f4_maximal_other

    def test_22_extend_with_multi_owner_event_creates_one_maximal_frontier(self):
        """
        Start with P:1, Q:1. Extend with PQ:2,2.
        Should result in one maximal frontier {P:PQ_sync, Q:PQ_sync}.
        """
        win = SlidingFrontierWindow(max_size=5)
        cand_p1 = win.extend(E('p1', {'P'}, {'P': 1}, set()))
        win.commit_and_prune_candidates(cand_p1)
        cand_q1 = win.extend(E('q1', {'Q'}, {'Q': 1}, set()))
        win.commit_and_prune_candidates(cand_q1)

        e_pq_sync = E('pq_s', {'P', 'Q'}, {'P': 2, 'Q': 2}, set())
        cand_sync = win.extend(e_pq_sync)
        win.commit_and_prune_candidates(cand_sync)

        assert len(win) == 1
        assert win.latest.events['P'] == e_pq_sync
        assert win.latest.events['Q'] == e_pq_sync

    def test_23_clear_resets_rs_tracking_if_active(self):
        """Test that clear also clears internal Rs tracking."""
        win = SlidingFrontierWindow()
        win.activate_optimized_pruning({'P'})
        f1 = Frontier({'A': E('a1', {'A'}, {'A': 1}, set())})
        win.insert(f1)
        if f1 in win._frontier_outgoing_processes:
            win._frontier_outgoing_processes[f1] = {'P'}

        assert f1 in win._frontier_outgoing_processes
        win.clear()
        assert len(win) == 0
        assert len(win._frontier_outgoing_processes) == 0

    def test_24_extend_empty_window_with_multi_owner(self):
        """Extend an empty window directly with a multi-owner event."""
        win = SlidingFrontierWindow()
        event_pq = E('pq1', {'P', 'Q'}, {'P': 1, 'Q': 1}, {'data'})

        candidates = win.extend(event_pq)
        win.commit_and_prune_candidates(candidates)

        assert len(win) == 1
        assert win.latest.events['P'] == event_pq
        assert win.latest.events['Q'] == event_pq
        assert holds(win.latest, 'data')

    def test_25_no_pruning_if_less_than_max_size_and_all_maximal_no_rs(self):
        """
        If Rs-pruning is off, and unique maximals are <= max_size, no items removed by size cap.
        Maximality filter still runs.
        """
        win = SlidingFrontierWindow(max_size=3)
        f_a = Frontier({'A': E('fa', {'A'}, {'A': 1}, set())})
        f_b = Frontier({'B': E('fb', {'B'}, {'B': 1}, set())})

        win.clear()
        # Manually set frontiers to two distinct, concurrent, maximal frontiers
        win.frontiers = [f_a, f_b]
        win.prune()  # De-dup (no change), Rs (off), Maximality (no change), Size cap (2<=3, no change)
        assert len(win) == 2
        assert f_a in win.frontiers
        assert f_b in win.frontiers

    def test_26_rs_pruning_not_active_no_effect(self):
        """If Rs-pruning is not active, it should have no effect even if conditions met."""
        win = SlidingFrontierWindow(max_size=5)
        # DO NOT call win.activate_optimized_pruning(...)

        event_a = E('a1_e', {'A'}, {'A': 1}, set())
        cand_a = win.extend(event_a)
        win.commit_and_prune_candidates(cand_a)

        # Try to manually set Rs data (this won't be used by prune if Rs is not active)
        frontier_a_in_window = Frontier({'A': event_a})  # Reconstruct to match what's in window
        if frontier_a_in_window in win._frontier_outgoing_processes:
            win._frontier_outgoing_processes[frontier_a_in_window] = {'P', 'Q'}

        cand_x = win.extend(E('x1_e', {'X'}, {'X': 1}, set()))
        win.commit_and_prune_candidates(cand_x)

        latest_f = win.latest
        # The latest frontier should be the merge of A:a1_e and X:x1_e
        assert 'A' in latest_f.events
        assert latest_f.events['A'].eid == 'a1_e'
        assert 'X' in latest_f.events
        assert latest_f.events['X'].eid == 'x1_e'

    def test_27_complex_extend_sequence_final_state(self):
        """
        A more involved sequence of single and multi-owner events.
        Focus on the final set of maximal frontiers.
        """
        win = SlidingFrontierWindow(max_size=3)

        e_p1 = E('p1', {'P'}, {'P': 1}, set())
        e_q1 = E('q1', {'Q'}, {'Q': 1}, set())
        e_r1 = E('r1', {'R'}, {'R': 1}, set())

        cand = win.extend(e_p1)
        win.commit_and_prune_candidates(cand)
        cand = win.extend(e_q1)
        win.commit_and_prune_candidates(cand)

        e_pq_s2 = E('pqs2', {'P', 'Q'}, {'P': 2, 'Q': 2}, set())
        cand = win.extend(e_pq_s2)
        win.commit_and_prune_candidates(cand)

        cand = win.extend(e_r1)
        win.commit_and_prune_candidates(cand)

        e_pr_s3 = E('prs3', {'P', 'R'}, {'P': 3, 'R': 2}, set())
        cand = win.extend(e_pr_s3)
        win.commit_and_prune_candidates(cand)

        assert len(win) == 1
        latest_f = win.latest
        assert latest_f.events['P'] == e_pr_s3
        assert latest_f.events['Q'] == e_pq_s2
        assert latest_f.events['R'] == e_pr_s3

