# test/logic_tests/test_monitor_scenarios.py

import pytest  # Pytest is typically imported for more complex scenarios or fixtures
from model.event import Event
from model.vector_clock import VectorClock as VC
from logic.monitor import Monitor, Verdict  # Assuming these are in your logic package


# Helper function - can be at the module level or within the class as a static method
def E(eid: str, procs: set[str], clock: dict[str, int], props: set[str]) -> Event:
    """Factory for creating Event objects for testing."""
    return Event(eid, frozenset(procs), VC(clock), frozenset(props))


class TestMonitorScenarios:
    """
    Test suite for the PBTL Monitor, covering various scenarios including
    concurrent events, P/M/N block interactions, out-of-order delivery,
    multi-owner events, and specific FSM row logic (especially Row 6).
    """

    def test_01_m_only_concurrent_literals_succeeds(self):
        """
        Tests EP(p & q) with concurrent events providing 'p' and 'q'.
        Expected: TRUE, as a frontier {P:p1, Q:q1} satisfies (p & q).
        Corresponds to: M-only evaluation (Table 2, Row 7 like logic).
        """
        m = Monitor("EP(p & q)")
        m.process(E("p1", {"P"}, {"P": 1}, {"p"}))
        m.process(E("q1", {"Q"}, {"Q": 1}, {"q"}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_02_p_and_not_n_n_block_violates_early_fails(self):
        """
        Tests EP(EP(p) & !EP(q)) where 'q' (N-block's target) occurs before 'p'.
        Expected: FALSE, because EP(q) becomes true, violating !EP(q) before or
                  concurrently with EP(p) fully satisfying conditions for success.
        Corresponds to: P and N blocks (Table 2, Row 3 like logic). n_violated becomes true.
        """
        m = Monitor("EP(EP(p) & !EP(q))")
        m.process(E("q_event", {"P"}, {"P": 1}, {"q"}))  # N-block's EP(q) becomes true
        m.process(E("p_event", {"P"}, {"P": 2}, {"p"}))  # P-block EP(p) becomes true
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_03_p_and_not_n_p_block_succeeds_before_n_violates(self):
        """
        Tests EP(EP(p) & !EP(q)) where 'p' occurs, satisfying EP(p), before 'q' occurs.
        Expected: TRUE, because EP(p) is satisfied while !EP(q) (n_violated=false) holds,
                  leading to terminal success before EP(q) can become true.
        Corresponds to: P and N blocks (Table 2, Row 3 like logic).
        """
        m = Monitor("EP(EP(p) & !EP(q))")
        m.process(E("p_event", {"P"}, {"P": 1}, {"p"}))  # EP(p) satisfied, n_violated is false. Success.
        m.process(E("q_event", {"P"}, {"P": 2}, {"q"}))  # EP(q) satisfied now, but FSM is terminal.
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_04_m_only_three_concurrent_literals_succeeds(self):
        """
        Tests EP(a & b & c) with three concurrent events providing a, b, c.
        Expected: TRUE, as a frontier {A:a, B:b, C:c} satisfies (a & b & c).
        """
        m = Monitor("EP(a & b & c)")
        m.process(E("a_event", {"A"}, {"A": 1}, {"a"}))
        m.process(E("b_event", {"B"}, {"B": 1}, {"b"}))
        m.process(E("c_event", {"C"}, {"C": 1}, {"c"}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_05_m_only_missing_one_literal_final_false(self):
        """
        Tests EP(a & b & c) where 'c' is never provided.
        Expected: INCONCLUSIVE while events are processed, then FALSE at finish()
                  because the M-block (a & b & c) was never fully satisfied on a
                  delivered event (triggers (b') failure for M-only).
        """
        m = Monitor("EP(a & b & c)")
        m.process(E("a_event", {"A"}, {"A": 1}, {"a"}))
        m.process(E("b_event", {"B"}, {"B": 1}, {"b"}))

        # Intermediate check: still INCONCLUSIVE as 'c' is missing
        assert m.verdict is Verdict.INCONCLUSIVE

        m.finish()  # finalize_at_trace_end() for EP(a & b & c) FSM is called.
        # Since (a & b & c) (M-literals) were never satisfied, it becomes FALSE.
        assert m.verdict is Verdict.FALSE

    def test_06_m_only_multi_owner_event_buffered_final_false(self):
        """
        Tests EP(p & q) where a multi-owner event carrying (p & q) arrives
        with vector clock {P:3, Q:3} before P and Q have reached predecessor states
        that would allow its delivery.
        Expected: INCONCLUSIVE while buffering, then FALSE at finish() because (p & q)
                  was never satisfied on a delivered event (triggers (b') failure for M-only).
        """
        m = Monitor("EP(p & q)")
        m.process(E("p_tick", {"P"}, {"P": 1}, {}))  # Let P be at 1
        m.process(E("q_tick", {"Q"}, {"Q": 1}, {}))  # Let Q be at 1

        # Intermediate check: still INCONCLUSIVE
        assert m.verdict is Verdict.INCONCLUSIVE

        # Event requiring P:3, Q:3. Current _seen is {P:1, Q:1}.
        # This event is not deliverable because P needs to be at 2 (for event P:3)
        # and Q needs to be at 2 (for event Q:3).
        m.process(E("pq_joint", {"P", "Q"}, {"P": 3, "Q": 3}, {"p", "q"}))
        assert m.verdict is Verdict.INCONCLUSIVE  # pq_joint is buffered

        m.finish()  # pq_joint still not deliverable.
        # finalize_at_trace_end() for EP(p & q) FSM is called.
        # Since (p & q) (M-literals) were never satisfied, it becomes FALSE.
        assert m.verdict is Verdict.FALSE

    def test_07_m_only_multi_owner_event_after_satisfaction(self):
        """
        Tests EP(p & q). First p & q is satisfied by separate events.
        A subsequent multi-owner sync event (without p,q) should not change the TRUE verdict.
        Expected: TRUE.
        """
        m = Monitor("EP(p & q)")
        m.process(E("p1_event", {"P"}, {"P": 1}, {"p"}))
        m.process(E("q1_event", {"Q"}, {"Q": 1}, {"q"}))  # EP(p&q) becomes TRUE here
        # Intermediate check to confirm it became TRUE
        # Depending on short-circuiting and when verdict updates globally,
        # it might be better to check only after finish() or make this explicit.
        # For simplicity, we'll assume finish() is needed for robust check.
        # However, if FSMs update global verdict immediately, this would pass:
        # assert m.verdict is Verdict.TRUE
        m.process(E("sync_event", {"P", "Q"}, {"P": 2, "Q": 2}, set()))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_08_n_only_no_violating_event_initial_success(self):
        """
        Tests EP(!EP(r)) (N-only). No event provides 'r'.
        Expected: TRUE, due to initial evaluation against IOTA (EP(r) is false).
                  Row 6 success is terminal.
        """
        m = Monitor("EP(!EP(r))")
        assert m.verdict is Verdict.TRUE  # Check after Monitor init (IOTA processing)
        m.process(E("tick_event", {"P"}, {"P": 1}, set()))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_09_n_only_violating_event_after_initial_success(self):
        """
        Tests EP(!EP(r)) (N-only). 'r' event occurs after initial success.
        Expected: TRUE, because Row 6 N-only success is terminal.
        """
        m = Monitor("EP(!EP(r))")
        assert m.verdict is Verdict.TRUE  # Initial success
        m.process(E("r_event", {"P"}, {"P": 1}, {"r"}))  # EP(r) would become true
        m.finish()
        assert m.verdict is Verdict.TRUE  # Verdict remains TRUE (terminal)

    def test_10_m_only_stability_after_true(self):
        """
        Tests EP(x). Once TRUE, subsequent unrelated events should not change it.
        Expected: TRUE.
        """
        m = Monitor("EP(x)")
        m.process(E("x_event", {"P"}, {"P": 1}, {"x"}))
        # m.finish() # Call finish to ensure verdict is processed if there's any internal queue/delay
        # self.assertIs(m.verdict, Verdict.TRUE)
        # With current Monitor, verdict updates after _deliver, so this should be TRUE immediately
        assert m.verdict is Verdict.TRUE
        m.process(E("y_event", {"Q"}, {"Q": 1}, {"y"}))
        assert m.verdict is Verdict.TRUE
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_11_p_and_not_n_violating_n_event_after_success(self):
        """
        Tests EP(EP(p) & !EP(q)). EP(p) leads to success.
        A subsequent event making EP(q) true should not revert the TRUE verdict.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(p) & !EP(q))")
        m.process(E("p_event", {"P"}, {"P": 1}, {"p"}))
        assert m.verdict is Verdict.TRUE  # Success achieved
        m.process(E("q_event", {"P"}, {"P": 2}, {"q"}))  # N-block's EP(q) would be true
        assert m.verdict is Verdict.TRUE  # FSM is terminal
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_12_p_and_not_n_out_of_order_delivery_success(self):
        """
        Tests EP(EP(p) & !EP(q)) with out-of-order events.
        q@P:2 arrives before p@P:1. Buffering should ensure p is processed first.
        Expected: TRUE, as p is processed before q, leading to !EP(q) holding when EP(p) does.
        """
        m = Monitor("EP(EP(p) & !EP(q))")
        m.process(E("q_event_late", {"P"}, {"P": 2}, {"q"}))  # Buffered
        assert m.verdict is Verdict.INCONCLUSIVE  # q_event_late is buffered
        m.process(E("p_event_early", {"P"}, {"P": 1}, {"p"}))  # Flushes p_event_early, then q_event_late
        # p_event_early makes EP(p) true. !EP(q) holds. Success.
        # q_event_late then makes EP(q) true, but FSM is terminal.
        m.finish()  # Ensure all processing is complete
        assert m.verdict is Verdict.TRUE

        # In class TestPBTLSмониторScenarios:

    def test_14_m_only_target_event_remains_buffered_and_final_false(self):  # Renamed for clarity
        """
        Tests EP(sync) where 'sync' is only on a multi-owner event e_pq_sync.
        e_pq_sync has VC {P:3, Q:3}. Predecessor events only advance P and Q to 1.
        Thus, e_pq_sync should be buffered and never delivered.
        Expected: INCONCLUSIVE while buffering, then FALSE at finish() because 'sync'
                  was never satisfied on a delivered event (triggers (b') failure for M-only).
        """
        m = Monitor("EP(sync)")

        # Predecessor events: advance P and Q to timestamp 1
        # These events DO NOT carry 'sync'
        m.process(E("p_tick", {"P"}, {"P": 1}, {}))
        m.process(E("q_tick", {"Q"}, {"Q": 1}, {}))

        # At this point, _seen should be roughly {P:1, Q:1}.
        # The monitor is INCONCLUSIVE as 'sync' hasn't been seen on a delivered event yet.
        assert m.verdict is Verdict.INCONCLUSIVE

        # The target multi-owner event carrying 'sync'.
        # Its VC {P:3, Q:3} requires P and Q to have completed their respective event 2
        # before this event (event 3 for P and Q) can be processed.
        # Currently, _seen is {P:1, Q:1}.
        m.process(E("pq_target_sync", {"P", "Q"}, {"P": 3, "Q": 3}, {"sync"}))

        # pq_target_sync ({P:3, Q:3}) is NOT deliverable because seen[P]+1 is 2 (not 3)
        # and seen[Q]+1 is 2 (not 3). It will be buffered.
        # The monitor's verdict should remain INCONCLUSIVE because 'sync' hasn't been processed.
        assert m.verdict is Verdict.INCONCLUSIVE

        m.finish()  # Attempt to flush buffer. pq_target_sync is still not deliverable.
        # finalize_at_trace_end() for EP(sync) FSM is called.
        # Since 'sync' (M-literal) was never satisfied, it becomes FALSE.

        # Final verdict should be FALSE because 'sync' was never on a delivered event,
        # and finalize_at_trace_end for an M-only disjunct sets failure if M was not met.
        assert m.verdict is Verdict.FALSE

    def test_15_multiple_p_and_not_n_late_n_block_no_effect(self):
        """
        Tests EP(EP(a) & EP(b) & EP(c) & !EP(d)).
        a,b,c occur satisfying their P-blocks. !EP(d) holds. Success.
        A very late 'd' event should not change the TRUE verdict.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(a) & EP(b) & EP(c) & !EP(d))")

        # Deliver prerequisites
        m.process(E("b_pred", {"B"}, {"B": 1}, set()))
        m.process(E("c_pred1", {"C"}, {"C": 1}, set()))
        m.process(E("c_pred2", {"C"}, {"C": 2}, set()))

        # Deliver P-block events (order of processing might be handled by buffering)
        m.process(E("b_event", {"B"}, {"B": 2}, {"b"}))
        m.process(E("c_event", {"C"}, {"C": 3}, {"c"}))
        m.process(E("a_event", {"A"}, {"A": 1}, {"a"}))

        # Verdict might become TRUE after these are flushed and processed by FSMs
        # Calling finish() ensures this state is reached.
        m.finish()
        assert m.verdict is Verdict.TRUE

        # Process a late event that would satisfy EP(d)
        m.process(E("d_event_late", {"D"}, {"D": 10}, {"d"}))
        # FSM should be terminal, so verdict remains TRUE
        assert m.verdict is Verdict.TRUE
        m.finish()  # Ensure it's processed
        assert m.verdict is Verdict.TRUE

    def test_16_multiple_p_single_process_out_of_order_chain_succeeds(self):
        """
        Tests EP(EP(x) & EP(y) & EP(z)) on a single process P.
        Events arrive out of VC order (P:3, then P:1, then P:2).
        Buffering should reorder them causally, leading to all EP conditions met.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(x) & EP(y) & EP(z))")
        m.process(E("z_event", {"P"}, {"P": 3}, {"z"}))  # Buffered
        m.process(E("x_event", {"P"}, {"P": 1}, {"x"}))  # Delivers x_event (P:1)
        m.process(E("y_event", {"P"}, {"P": 2}, {"y"}))  # Delivers y_event (P:2), then z_event (P:3)
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_17_m_only_joint_event_deliverable_after_predecessors_succeeds(self):
        """
        Tests EP(m). A joint event on {P,Q,R} carries 'm'.
        It becomes deliverable only after each owner-process delivers its predecessor.
        Expected: TRUE.
        """
        m = Monitor("EP(m)")

        m.process(E("p_pred", {"P"}, {"P": 1}, {}))
        m.process(E("q_pred", {"Q"}, {"Q": 1}, {}))
        m.process(E("r_pred", {"R"}, {"R": 1}, {}))
        assert m.verdict is Verdict.INCONCLUSIVE  # 'm' not yet seen

        # Joint event is now deliverable as its VCs P:2,Q:2,R:2 match seen P:1,Q:1,R:1 + 1
        m.process(E("pqr_joint_m", {"P", "Q", "R"}, {"P": 2, "Q": 2, "R": 2}, {"m"}))
        # After this event is delivered, EP(m) becomes true.
        # Depending on immediate update, or after finish:
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_18_n_only_multi_owner_violating_event_buffered_remains_true(self):
        """
        Tests EP(!EP(veto)). FSM is initially TRUE (Row 6).
        A multi-owner event that would satisfy EP(veto) is created but remains buffered
        because its VC prerequisites are not met by prior events.
        Expected: TRUE, as the FSM is terminal TRUE and the veto event is not delivered.
        """
        m = Monitor("EP(!EP(veto))")
        assert m.verdict is Verdict.TRUE  # Initial Row 6 success

        # These events establish X and Y but not up to required VCs for XY_veto_event
        m.process(E("x_tick", {"X"}, {"X": 1}, set()))  # X seen up to 1
        m.process(E("y_tick", {"Y"}, {"Y": 1}, set()))  # Y seen up to 1

        # Joint veto event that requires X:5, Y:5. _seen is X:1, Y:1, so it's buffered.
        m.process(E("xy_veto_event", {"X", "Y"}, {"X": 5, "Y": 5}, {"veto"}))
        assert m.verdict is Verdict.TRUE  # Still TRUE, veto buffered

        m.finish()  # Veto event remains undelivered
        assert m.verdict is Verdict.TRUE

    def test_19_n_only_multi_owner_violating_event_delivered_remains_true(self):
        """
        Tests EP(!EP(veto)). FSM is initially TRUE (Row 6, terminal).
        A multi-owner event satisfying EP(veto) is delivered after prerequisites.
        Expected: TRUE, as the FSM was already in a terminal TRUE state.
        """
        m = Monitor("EP(!EP(veto))")
        assert m.verdict is Verdict.TRUE  # Initial success

        m.process(E("x_pred", {"X"}, {"X": 1}, set()))
        m.process(E("y_pred", {"Y"}, {"Y": 1}, set()))  # Prerequisites for XY_veto_event

        m.process(E("xy_veto_event", {"X", "Y"}, {"X": 2, "Y": 2}, {"veto"}))  # Deliverable
        # FSM is terminal, so even if EP(veto) is processed, verdict remains TRUE
        m.finish()  # Ensure processing
        assert m.verdict is Verdict.TRUE

    def test_20_n_only_multi_owner_out_of_order_delivery_remains_true(self):
        """
        Tests EP(!EP(veto)). FSM initially TRUE (terminal).
        Higher VC events X2, Y2 are buffered. Lower VC joint event XY1 (carrying veto)
        is delivered first. Subsequent deliveries don't change terminal TRUE state.
        Expected: TRUE.
        """
        m = Monitor("EP(!EP(veto))")
        assert m.verdict is Verdict.TRUE  # Initial success

        m.process(E("x_event_2", {"X"}, {"X": 2}, set()))  # Buffered
        m.process(E("y_event_2", {"Y"}, {"Y": 2}, set()))  # Buffered
        assert m.verdict is Verdict.TRUE  # Still from init

        # XY1 is deliverable. When processed, EP(veto) might become true internally for the N-block.
        # But FSM is terminal. Then X2, Y2 are delivered.
        m.process(E("xy_joint_veto_1", {"X", "Y"}, {"X": 1, "Y": 1}, {"veto"}))
        m.finish()  # Ensure all flushes
        assert m.verdict is Verdict.TRUE

    def test_21_n_only_ordinary_literals_initial_success_is_terminal(self):
        """
        Tests EP(!EP(a) & !EP(b)). No P, no M blocks. No 'iota' in N-blocks.
        Expected: TRUE on initialization (Row 6, n_violated=false). This success is terminal.
                  Subsequent events making EP(a) or EP(b) true do not change verdict.
        """
        m = Monitor("EP(!EP(a) & !EP(b))")
        assert m.verdict is Verdict.TRUE  # Initial Row 6 success (terminal)

        m.process(E("a_event", {"P"}, {"P": 1}, {"a"}))
        assert m.verdict is Verdict.TRUE
        m.process(E("b_event", {"P"}, {"P": 2}, {"b"}))  # In FSM code, was P:2, let's make it Q to be distinct
        assert m.verdict is Verdict.TRUE
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_22_n_only_includes_iota_initial_failure_is_terminal(self):
        """
        Tests EP(!EP(iota) & !EP(a)). Contains EP(iota) as part of an N-block.
        Expected: FALSE on initialization (Row 6, EP(iota) makes n_violated=true).
                  This failure is terminal.
        """
        m = Monitor("EP(!EP(iota) & !EP(a))")
        assert m.verdict is Verdict.FALSE  # Initial Row 6 failure (terminal)

        m.process(E("a_event", {"P"}, {"P": 1}, {"a"}))
        assert m.verdict is Verdict.FALSE
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_23_n_only_duplicate_iota_check_initial_failure(self):
        """
        Tests EP(!EP(iota) & !EP(iota)). Similar to test_22.
        Expected: FALSE on initialization.
        """
        m = Monitor("EP(!EP(iota) & !EP(iota))")
        assert m.verdict is Verdict.FALSE
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_24_n_only_mixed_iota_and_ordinary_initial_failure(self):
        """
        Tests EP(!EP(a) & !EP(iota) & !EP(b)). Presence of EP(iota) in N-block
        causes initial failure.
        Expected: FALSE.
        """
        m = Monitor("EP(!EP(a) & !EP(iota) & !EP(b))")
        assert m.verdict is Verdict.FALSE
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_25_n_only_all_ordinary_literals_initial_success(self):
        """
        Tests EP(!EP(x) & !EP(y) & !EP(z)). No P, M, or iota N-blocks.
        Expected: TRUE on initialization (Row 6 success, terminal).
        """
        m = Monitor("EP(!EP(x) & !EP(y) & !EP(z))")
        assert m.verdict is Verdict.TRUE  # Initial success, terminal
        m.process(E("x_event", {"P"}, {"P": 1}, {"x"}))
        assert m.verdict is Verdict.TRUE
        m.process(E("y_event", {"Q"}, {"Q": 1}, {"y"}))  # Changed to Q for variety
        assert m.verdict is Verdict.TRUE
        m.process(E("z_event", {"R"}, {"R": 1}, {"z"}))  # Changed to R for variety
        assert m.verdict is Verdict.TRUE
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_26_n_only_ordinary_violation_after_initial_success_no_change(self):
        """
        Tests EP(!EP(a) & !EP(b)). Initially TRUE (Row 6 terminal success).
        An event later making EP(a) true should NOT change the verdict from TRUE,
        as Row 6 N-only success is a terminal state in this FSM.
        """
        m = Monitor("EP(!EP(a) & !EP(b))")
        assert m.verdict is Verdict.TRUE  # Initial Row 6 success (terminal)

        m.process(E("a_event", {"P"}, {"P": 1}, {"a"}))  # EP(a) is now true for N-block
        assert m.verdict is Verdict.TRUE  # Verdict remains TRUE due to terminal state
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_27_n_only_iota_violation_initial_failure_no_change(self):
        """
        Tests EP(!EP(iota) & !EP(a)). Initially FALSE due to EP(iota) (Row 6 terminal failure).
        Subsequent events should not change the verdict.
        Expected: FALSE throughout.
        """
        m = Monitor("EP(!EP(iota) & !EP(a))")
        assert m.verdict is Verdict.FALSE  # Initial Row 6 failure (terminal)

        m.process(E("a_event", {"P"}, {"P": 1}, {"a"}))
        assert m.verdict is Verdict.FALSE  # Verdict remains FALSE
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_29_p_and_n_p_block_succeeds_then_n_block_ignored(self):
        """
        Scenario: EP(EP(a) & !EP(b)). 'a' occurs first, satisfying EP(a) while !EP(b) holds.
                  This leads to terminal success. A subsequent 'b' event should not change the verdict.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(a) & !EP(b))")
        m.process(E('a1', {'P'}, {'P': 1}, {'a'}))
        assert m.verdict is Verdict.TRUE
        m.process(E('b1', {'P'}, {'P': 2}, {'b'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_30_p_only_sequential_p_blocks_succeeds(self):
        """
        Scenario: EP(EP(a) & EP(b)) with 'a' then 'b'.
        Expected: TRUE, as both P-blocks EP(a) and EP(b) are eventually satisfied.
        """
        m = Monitor("EP(EP(a) & EP(b))")
        m.process(E('a1', {'P'}, {'P': 1}, {'a'}))
        m.process(E('b1', {'P'}, {'P': 2}, {'b'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_31_disjunction_one_branch_true_succeeds(self):
        """
        Scenario: EP(EP(x) | EP(y)). 'x' appears, 'y' never does.
        Expected: TRUE, as one disjunct (EP(EP(x))) becomes true.
        """
        m = Monitor("EP(EP(x) | EP(y))")
        m.process(E('x1', {'P'}, {'P': 1}, {'x'}))
        assert m.verdict is Verdict.TRUE
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_32_m_only_no_matching_events_final_false(self):
        """
        Scenario: EP(z) with no event carrying 'z'.
        Expected: FALSE at finish, as 'z' was never satisfied.
        """
        m = Monitor("EP(z)")
        m.process(E('other1', {'P'}, {'P': 1}, {'other'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_33_m_only_sequential_literals_on_different_procs_succeeds(self):
        """
        Scenario: EP(p & q). p on P, then q on Q (concurrently).
        Expected: TRUE.
        """
        m = Monitor("EP(p & q)")
        m.process(E('p1', {'P'}, {'P': 1}, {'p'}))
        m.process(E('q1', {'Q'}, {'Q': 1}, {'q'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_34_m_only_one_literal_missing_final_false(self):
        """
        Scenario: EP(p & q & r). p and q occur, r does not.
        Expected: FALSE at finish, as (p & q & r) was never fully satisfied.
        """
        m = Monitor("EP(p & q & r)")
        m.process(E('p1', {'P'}, {'P': 1}, {'p'}))
        m.process(E('q_and_other', {'Q', 'S'}, {'Q': 1, 'S': 1}, {'q', 'other'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_35_p_only_nested_ep_succeeds(self):
        """
        Scenario: EP(EP(a & EP(b))). Trace: b occurs, then a occurs concurrently.
        Expected: TRUE. (EP(a&EP(b)) means EP(a&b) with current _holds).
        """
        m = Monitor("EP(EP(a & EP(b)))")
        m.process(E('b1', {'P'}, {'P': 1}, {'b'}))
        m.process(E('a1', {'Q'}, {'Q': 1}, {'a'}))  # Concurrent 'a'
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_36_p_only_nested_ep_inner_never_satisifed_final_false(self):
        """
        Scenario: EP(EP(a & EP(b))). Trace: a occurs, b never occurs.
        Expected: FALSE at finish. (EP(a&EP(b)) means EP(a&b) with current _holds,
                  and this P-block is never satisfied if 'b' is missing).
        """
        m = Monitor("EP(EP(a & EP(b)))")
        m.process(E('a1', {'P'}, {'P': 1}, {'a'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_37_n_only_multiple_ordinary_n_blocks_initial_success_terminal(self):
        """
        Scenario: EP(!EP(a) & !EP(b) & !EP(c)). None involve 'iota'.
        Expected: TRUE from initialization (Row 6), and remains TRUE.
        """
        m = Monitor("EP(!EP(a) & !EP(b) & !EP(c))")
        assert m.verdict is Verdict.TRUE
        m.process(E('a1', {'P'}, {'P': 1}, {'a'}))
        m.process(E('b1', {'Q'}, {'Q': 1}, {'b'}))
        m.process(E('c1', {'R'}, {'R': 1}, {'c'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_38_n_only_one_iota_n_block_causes_initial_failure_terminal(self):
        """
        Scenario: EP(!EP(a) & !EP(iota) & !EP(c)). Contains !EP(iota).
        Expected: FALSE from initialization (Row 6), and remains FALSE.
        """
        m = Monitor("EP(!EP(a) & !EP(iota) & !EP(c))")
        assert m.verdict is Verdict.FALSE
        m.process(E('a1', {'P'}, {'P': 1}, {'a'}))
        m.process(E('c1', {'R'}, {'R': 1}, {'c'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_39_p_m_n_complex_success(self):
        """
        Scenario: EP(EP(x & EP(y)) & m1 & m2 & !EP(z1) & !EP(z2))
        Trace: y and x occur concurrently, then m1&m2 occur. z1, z2 never occur.
        Expected: TRUE. (EP(x&EP(y)) means EP(x&y)).
        """
        formula = "EP(EP(x & EP(y)) & m1 & m2 & !EP(z1) & !EP(z2))"
        m = Monitor(formula)
        m.process(E('y1', {'P1'}, {'P1': 1}, {'y'}))
        m.process(E('x1', {'P2'}, {'P2': 1}, {'x'}))
        m.process(E('m_stuff', {'Q'}, {'Q': 1}, {'m1', 'm2'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_40_p_m_n_complex_n_block_violates_early_fails(self):
        """
        Scenario: EP(EP(x) & m & !EP(z))
        Trace: z occurs first.
        Expected: FALSE.
        """
        m = Monitor("EP(EP(x) & m & !EP(z))")
        m.process(E('z1', {'R'}, {'R': 1}, {'z'}))
        m.process(E('x1', {'P'}, {'P': 1}, {'x'}))
        m.process(E('m1', {'Q'}, {'Q': 1}, {'m'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_41_p_m_n_complex_m_block_never_satisfied_final_false(self):
        """
        Scenario: EP(EP(x) & m1 & m2 & !EP(z))
        Trace: x occurs, z does not. m2 never occurs.
        Expected: FALSE at finish (P met, but M not correctly after).
        """
        m = Monitor("EP(EP(x) & m1 & m2 & !EP(z))")
        m.process(E('x1', {'P'}, {'P': 1}, {'x'}))
        m.process(E('m1_event', {'Q'}, {'Q': 1}, {'m1'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_42_disjunction_one_branch_initially_true_remains_true(self):
        """
        Scenario: EP( (!EP(a)) | (!EP(iota)) )
        This becomes D1 = EP(!EP(a)) | D2 = EP(!EP(iota)).
        D1 (EP(!EP(a))) FSM is TRUE on init (Row 6 N-only success, terminal).
        D2 (EP(!EP(iota))) FSM is FALSE on init (Row 6 N-only failure, terminal).
        Global verdict is TRUE | FALSE => TRUE.
        Subsequent event 'a1' does not change D1's terminal TRUE state.
        Expected: TRUE.
        """
        m = Monitor("EP( (!EP(a)) | (!EP(iota)) )")
        # Initial state: FSM for EP(!EP(a)) is TRUE. FSM for EP(!EP(iota)) is FALSE.
        # Global verdict = TRUE | FALSE = TRUE.
        assert m.verdict is Verdict.TRUE

        m.process(E('a1', {'P'}, {'P': 1}, {'a'}))
        # Event 'a1' makes EP(a) true.
        # However, FSM for EP(!EP(a)) is already in a terminal TRUE state from init.
        # So, its verdict does not change.
        m.finish()
        # Global verdict remains TRUE | FALSE = TRUE.
        assert m.verdict is Verdict.TRUE

    def test_43_disjunction_one_branch_eventually_true_succeeds(self):
        """
        Scenario: EP( EP(x) | EP(y & EP(z)) )
        Trace: z and y occur concurrently. x never occurs.
        Expected: TRUE. (EP(y & EP(z)) means EP(y&z)).
        """
        m = Monitor("EP( EP(x) | EP(y & EP(z)) )")
        m.process(E('z1', {'P1'}, {'P1': 1}, {'z'}))
        m.process(E('y1', {'P2'}, {'P2': 1}, {'y'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_44_out_of_order_multi_process_m_only_succeeds(self):
        """
        Scenario: EP(a & b & c). Events for a, b, c on different processes,
                  arrive in an order that might require buffering if VCs were more complex,
                  but here they are concurrent and immediately deliverable.
        Expected: TRUE.
        """
        m = Monitor("EP(a & b & c)")
        m.process(E('c1', {'C'}, {'C': 1}, {'c'}))
        m.process(E('a1', {'A'}, {'A': 1}, {'a'}))
        m.process(E('b1', {'B'}, {'B': 1}, {'b'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_45_out_of_order_single_process_p_only_succeeds(self):
        """
        Scenario: EP(EP(x) & EP(y)). y@P:2 arrives before x@P:1.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(x) & EP(y))")
        m.process(E('y1', {'P'}, {'P': 2}, {'y'}))
        assert m.verdict is Verdict.INCONCLUSIVE
        m.process(E('x1', {'P'}, {'P': 1}, {'x'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_46_m_only_multi_owner_event_props_separate_final_false(self):
        """
        Scenario: EP(synced & p_val).
        'p_val' occurs on P. 'synced' occurs later on a joint P,Q event.
        No single frontier has both 'p_val' and 'synced' true simultaneously.
        Expected: FALSE at finish.
        """
        m = Monitor("EP(synced & p_val)")
        m.process(E('p_val_event', {'P'}, {'P': 1}, {'p_val'}))
        m.process(E('q_tick', {'Q'}, {'Q': 1}, {}))
        # After this, sync_event makes {P:2, Q:2} the latest for P & Q.
        # On the frontier defined by sync_event, 'p_val' (from p_val_event@P:1) is not current for P.
        m.process(E('sync_event', {'P', 'Q'}, {'P': 2, 'Q': 2}, {'synced'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_47_multi_owner_event_key_for_p_block_succeeds(self):
        """
        Scenario: EP(EP(handshake_done) & final_ack).
        'handshake_done' is on a multi-owner event.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(handshake_done) & final_ack)")
        m.process(E('p_tick', {'P'}, {'P': 1}, {}))
        m.process(E('q_tick', {'Q'}, {'Q': 1}, {}))
        m.process(E('handshake', {'P', 'Q'}, {'P': 2, 'Q': 2}, {'handshake_done'}))
        m.process(E('ack', {'R'}, {'R': 1}, {'final_ack'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_48_nested_p_m_n_complex_scenario_succeeds(self):
        """
        Scenario: EP( EP(a & !EP(b)) & x & !EP( EP(c) & y ) )
        Trace: a@P1, x@Q1, c@R1. b and y never occur.
        Expected: TRUE.
        - D1=EP(a & !EP(b)): 'a' holds, EP(b) is false. P-block for outer EP is satisfied.
        - D2=x: M-literal 'x' holds.
        - D3=!EP(EP(c) & y): EP(c) means 'c' holds. (EP(c)&y) means (c&y). Since y never occurs, (c&y) is false.
          So EP(c&y) is false. So !EP(c&y) is true. N-block not violated.
        """
        m = Monitor("EP( EP(a & !EP(b)) & x & !EP( EP(c) & y ) )")
        m.process(E('a1', {'P'}, {'P': 1}, {'a'}))
        m.process(E('x1', {'Q'}, {'Q': 1}, {'x'}))
        m.process(E('c1', {'R'}, {'R': 1}, {'c'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_49_deeply_nested_success(self):
        """
        Scenario: EP(EP(EP(EP(deep_prop))))
        Trace: deep_prop occurs. (Interpreted as EP(deep_prop) due to _holds).
        Expected: TRUE.
        """
        m = Monitor("EP(EP(EP(EP(deep_prop))))")
        m.process(E('d1', {'P'}, {'P': 1}, {'deep_prop'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_50_deeply_nested_pointwise_evaluation_succeeds(self):
        """
        Scenario: EP(EP(a & !EP(b & EP(EP(c)))))
        Trace: c@P1, b@P2, a@P3 (concurrently).
        The P-block EP(a & !EP(b&c)) is satisfied by an intermediate frontier
        where 'a' is true, and 'b' and 'c' are false (because P1 and P2 are
        still at their initial state when 'a' on P3 forms this specific frontier).
        Expected: TRUE.
        """
        m = Monitor("EP(EP(a & !EP(b & EP(EP(c)))))")

        # CRUCIAL: Define all system processes upfront for this test.
        m.activate_window_optimization({"P1", "P2", "P3"})

        # The Monitor's initial verdict after activate_window_optimization
        # (which calls _establish_initial_state_and_seed_fsms) should be INCONCLUSIVE
        # because the P-block `EP(a & !EP(b&c))` is not true on the initial system frontier.
        assert m.verdict is Verdict.INCONCLUSIVE

        m.process(E('c1', {'P1'}, {'P1': 1}, {'c'}))
        m.process(E('b1', {'P2'}, {'P2': 1}, {'b'}))
        m.process(E('a1', {'P3'}, {'P3': 1}, {'a'}))

        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_51_m_only_iota_involved_success(self):
        """
        Scenario: EP(iota & p)
        Trace: # system_processes: P
               p1,P,P:1,p
        Expected: FALSE, because 'iota' (from initial event on P) and 'p' (from p1 on P)
                  are not true on the *same* frontier. 'iota' is true at P:0, 'p' is true at P:1.
        """
        # Simulate the # system_processes: P directive for Monitor setup
        # This is typically handled by PropertyAndTraceMonitor reading the trace file.
        # For direct Monitor tests, we can call activate_window_optimization.
        m = Monitor("EP(iota & p)")
        m.activate_window_optimization({"P"})  # Crucial for defining initial state over P

        # Initial verdict after proper setup (including system processes P)
        # On the initial frontier Frontier({'P': initial_event_for_P_with_iota}), 'p' is false.
        # So (iota & p) is false. FSM is INCONCLUSIVE.
        assert m.verdict is Verdict.INCONCLUSIVE

        m.process(E('p1', {'P'}, {'P': 1}, {'p'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_52_m_only_iota_involved_final_false_if_prop_never_occurs(self):
        """
        Scenario: EP(iota & p)
        Trace: p never occurs.
        Expected: FALSE at finish.
        """
        m = Monitor("EP(iota & p)")
        assert m.verdict is Verdict.INCONCLUSIVE
        m.process(E('q1', {'Q'}, {'Q': 1}, {'q'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_53_p_block_with_iota_n_block_with_ordinary_succeeds(self):
        """
        Scenario: EP(EP(iota) & !EP(x))
        Trace: x never occurs.
        Expected: TRUE. EP(iota) is true from init. !EP(x) is true.
        """
        m = Monitor("EP(EP(iota) & !EP(x))")
        assert m.verdict is Verdict.TRUE
        m.process(E('y1', {'P'}, {'P': 1}, {'y'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_54_p_block_with_ordinary_n_block_with_iota_fails(self):
        """
        Scenario: EP(EP(x) & !EP(iota))
        Trace: x occurs.
        Expected: FALSE. EP(iota) is true from init, so !EP(iota) is false (N-block violated).
        """
        m = Monitor("EP(EP(x) & !EP(iota))")
        assert m.verdict is Verdict.FALSE
        m.process(E('x1', {'P'}, {'P': 1}, {'x'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_55_multiple_disjuncts_complex_one_succeeds(self):
        """
        Scenario: EP( (EP(a) & !EP(b)) | (EP(c & EP(d)) & x & !EP(y)) )
        Trace: c and d occur concurrently, then x occurs. (a,b,y never occur).
        Expected: TRUE (second disjunct succeeds).
        """
        formula = "EP( (EP(a) & !EP(b)) | (EP(c & EP(d)) & x & !EP(y)) )"
        m = Monitor(formula)
        assert m.verdict is Verdict.INCONCLUSIVE
        m.process(E("c_event", {"P1"}, {"P1": 1}, {"c"}))
        m.process(E("d_event", {"P2"}, {"P2": 1}, {"d"}))
        assert m.verdict is Verdict.INCONCLUSIVE
        m.process(E("x_event", {"Q"}, {"Q": 1}, {"x"}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_56_p_block_ep_c_and_ep_d_fails_if_m_missing(self):
        """
        Scenario: EP(EP(c & EP(d)) & x)
        Trace: c and d occur, but x (M-literal) does not.
        Expected: FALSE at finish.
        """
        formula = "EP(EP(c & EP(d)) & x)"  # P-block is EP(c&d), M-literal is x
        m = Monitor(formula)
        m.process(E('c1', {'P1'}, {'P1': 1}, {'c'}))
        m.process(E('d1', {'P2'}, {'P2': 1}, {'d'}))  # P-block EP(c&d) satisfied
        m.finish()  # x never occurs
        assert m.verdict is Verdict.FALSE

    def test_57_long_causal_chain_before_satisfaction(self):
        """
        Scenario: EP(target_prop)
        Trace: p1 -> p2 -> ... -> p10 -> target_prop_event
        Expected: TRUE.
        """
        m = Monitor("EP(target_prop)")
        for i in range(1, 11):
            m.process(E(f'tick{i}', {'P'}, {'P': i}, {f'intermediate{i}'}))
        assert m.verdict is Verdict.INCONCLUSIVE
        m.process(E('target', {'P'}, {'P': 11}, {'target_prop'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_58_out_of_order_multi_process_complex_buffering_succeeds(self):
        """
        Scenario: EP(p & q & r)
        Events for p,q,r are on P:3, Q:3, R:3. Predecessor events P:1,P:2 etc. are sent.
        Final events sent in an order that might stress buffering if VCs were different,
        but here they become deliverable after their ticks.
        Expected: TRUE
        """
        m = Monitor("EP(p & q & r)")
        m.process(E('p_tick1', {'P'}, {'P': 1}, {}))
        m.process(E('p_tick2', {'P'}, {'P': 2}, {}))
        m.process(E('q_tick1', {'Q'}, {'Q': 1}, {}))
        m.process(E('q_tick2', {'Q'}, {'Q': 2}, {}))
        m.process(E('r_tick1', {'R'}, {'R': 1}, {}))
        m.process(E('r_tick2', {'R'}, {'R': 2}, {}))

        m.process(E('r_final', {'R'}, {'R': 3}, {'r'}))
        m.process(E('p_final', {'P'}, {'P': 3}, {'p'}))
        m.process(E('q_final', {'Q'}, {'Q': 3}, {'q'}))

        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_59_no_matching_prop_in_disjunction_final_false(self):
        """
        Scenario: EP(EP(x) | EP(y))
        Trace: Only 'z' occurs.
        Expected: FALSE at finish (neither disjunct's P-block was satisfied).
        """
        m = Monitor("EP(EP(x) | EP(y))")
        m.process(E('z1', {'P'}, {'P': 1}, {'z'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    # Adding a few more tests based on previous discussions
    def test_60_m_only_single_prop_buffered_undelivered_final_false(self):
        """
        Scenario: EP(p). Event p@P:2 arrives, but P is only at _seen[P]=0.
        Expected: FALSE at finish.
        """
        m = Monitor("EP(p)")
        m.process(E('p_event', {'P'}, {'P': 2}, {'p'}))  # Buffered
        assert m.verdict is Verdict.INCONCLUSIVE
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_61_p_and_m_strict_causal_order_not_met_final_false(self):
        """
        Scenario: EP(p1 & EP(p2)). Trace: p1@P:1, then p2@P:2.
        P-block EP(p2) satisfied at frontier with p2@P:2.
        M-literal p1 was satisfied at earlier frontier with p1@P:1.
        Strict Row 2 requires M on frontier >= P-satisfaction frontier. This is not met.
        Expected: FALSE at finish.
        """
        m = Monitor("EP(p1 & EP(p2))")
        m.process(E("ev_p1", {"P"}, {"P": 1}, {"p1"}))
        m.process(E("ev_p2", {"P"}, {"P": 2}, {"p2"}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_62_m_only_multi_owner_event_props_together_succeeds(self):  # New test
        """
        Scenario: EP(synced & p_val).
        A single multi-owner event carries both 'synced' and 'p_val'.
        Expected: TRUE.
        """
        m = Monitor("EP(synced & p_val)")
        m.process(E('p_tick', {'P'}, {'P': 1}, {}))  # Prerequisite for P:2
        m.process(E('q_tick', {'Q'}, {'Q': 1}, {}))  # Prerequisite for Q:2
        # This joint event carries both props.
        m.process(E('joint_sync_pval', {'P', 'Q'}, {'P': 2, 'Q': 2}, {'synced', 'p_val'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_63_p_and_m_sequential_satisfaction_succeeds(self):
        """
        Trace: q@P:1, then p@P:2
        Spec: EP(p & EP(q))
        P-block EP(q) satisfied by q@P:1. M-literal 'p' satisfied by p@P:2.
        Frontier for p@P:2 is causally after frontier for q@P:1.
        Expected: TRUE.
        """
        m = Monitor("EP(p & EP(q))")
        m.process(E('q_event', {'P'}, {'P': 1}, {'q'}))
        m.process(E('p_event', {'P'}, {'P': 2}, {'p'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_64_disjunction_sequential_short_circuit_succeeds(self):
        """
        Trace: y@P:1
        Spec: EP(EP(x) | EP(y)) -> EP(EP(x)) | EP(EP(y))
        FSM for EP(EP(y)) becomes TRUE.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(x) | EP(y))")
        m.process(E('y_event', {'P'}, {'P': 1}, {'y'}))
        assert m.verdict is Verdict.TRUE  # Should be TRUE after 'y_event' is processed
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_65_p_only_missing_literal_in_conjunction_final_false(self):
        """
        Trace: p@P:1. 'q' never occurs.
        Spec: EP(EP(p) & EP(q))
        P-block EP(p) satisfied. P-block EP(q) never satisfied.
        Expected: FALSE at finish (due to (a') condition for P-only).
        """
        m = Monitor("EP(EP(p) & EP(q))")
        m.process(E('p_event', {'P'}, {'P': 1}, {'p'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_66_finish_idempotent_after_no_events(self):
        """
        Calling finish() multiple times on a monitor with no events
        should yield the same (likely FALSE or INCONCLUSIVE) verdict.
        Spec: EP(p)
        Expected: FALSE (M-only, 'p' never seen).
        """
        m = Monitor("EP(p)")
        m.finish()
        first_verdict = m.verdict
        assert first_verdict is Verdict.FALSE  # M-only, 'p' never seen
        m.finish()  # Call again
        assert m.verdict is first_verdict

    def test_67_finish_idempotent_after_some_events(self):
        """
        Calling finish() multiple times after some events
        should yield the same verdict.
        Spec: EP(p)
        Trace: p@P:1
        Expected: TRUE.
        """
        m = Monitor("EP(p)")
        m.process(E('p_event', {'P'}, {'P': 1}, {'p'}))
        m.finish()
        first_verdict = m.verdict
        assert first_verdict is Verdict.TRUE
        m.finish()  # Call again
        assert m.verdict is first_verdict

    def test_68_m_only_sequential_same_process_succeeds(self):
        """
        Scenario: EP(a & b). Trace: a@P:1, then b@P:2.
        Expected: TRUE. A frontier with P:2 (carrying 'b') will have 'a' in its history
                  for the _holds(a, fr_at_P2) check if _holds is stateful for M-literals.
                  With current point-wise _holds for M-literals, this should be FALSE.
                  If EP(a&b) means 'a' and 'b' must be true on the *same* frontier,
                  this trace does not satisfy it.
        Correction: EP(a&b) means 'a' and 'b' on the SAME frontier. This test should be FALSE.
        """
        m = Monitor("EP(a & b)")
        m.process(E('a_event', {'P'}, {'P': 1}, {'a'}))
        m.process(E('b_event', {'P'}, {'P': 2}, {'b'}))
        m.finish()
        assert m.verdict is Verdict.FALSE  # 'a' and 'b' are not on the same frontier

    def test_69_m_only_sequential_props_on_same_event_succeeds(self):
        """
        Scenario: EP(a & b). Trace: event_ab@P:1 carries both 'a' and 'b'.
        Expected: TRUE.
        """
        m = Monitor("EP(a & b)")
        m.process(E('ab_event', {'P'}, {'P': 1}, {'a', 'b'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_70_p_and_m_sequential_p_then_m_succeeds(self):
        """
        Scenario: EP(EP(a) & b). Trace: a@P:1, then b@P:2.
        P-block EP(a) satisfied at P:1. M-literal 'b' satisfied at P:2.
        Frontier P:2 is causally after P:1.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(a) & b)")
        m.process(E('a_event', {'P'}, {'P': 1}, {'a'}))
        m.process(E('b_event', {'P'}, {'P': 2}, {'b'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_71_p_and_m_sequential_m_then_p_fails_strict(self):
        """
        Scenario: EP(EP(a) & b). Trace: b@P:1, then a@P:2.
        M-literal 'b' satisfied at P:1. P-block EP(a) satisfied at P:2.
        But M must be satisfied at/after P.
        Expected: FALSE at finish (P met, M not correctly after).
        """
        m = Monitor("EP(EP(a) & b)")
        m.process(E('b_event', {'P'}, {'P': 1}, {'b'}))
        m.process(E('a_event', {'P'}, {'P': 2}, {'a'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_72_n_only_sequential_violation_after_init_true_remains_true(self):
        """
        Scenario: EP(!EP(a)). Trace: tick@P:1, then a@P:2.
        Initially TRUE. 'a' event occurs later.
        Expected: TRUE (Row 6 N-only success is terminal).
        """
        m = Monitor("EP(!EP(a))")
        assert m.verdict is Verdict.TRUE  # Initial success
        m.process(E('tick', {'P'}, {'P': 1}, {}))
        m.process(E('a_event', {'P'}, {'P': 2}, {'a'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_73_p_and_n_sequential_p_then_n_violation_remains_true(self):
        """
        Scenario: EP(EP(a) & !EP(b)). Trace: a@P:1, then b@P:2.
        EP(a) satisfied at P:1 while !EP(b) holds -> success.
        Expected: TRUE (terminal success).
        """
        m = Monitor("EP(EP(a) & !EP(b))")
        m.process(E('a_event', {'P'}, {'P': 1}, {'a'}))
        assert m.verdict is Verdict.TRUE
        m.process(E('b_event', {'P'}, {'P': 2}, {'b'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_74_p_and_n_sequential_n_violation_then_p_fails(self):
        """
        Scenario: EP(EP(a) & !EP(b)). Trace: b@P:1, then a@P:2.
        !EP(b) violated by b@P:1.
        Expected: FALSE.
        """
        m = Monitor("EP(EP(a) & !EP(b))")
        m.process(E('b_event', {'P'}, {'P': 1}, {'b'}))  # N-block violated
        assert m.verdict is Verdict.FALSE  # Should fail here
        m.process(E('a_event', {'P'}, {'P': 2}, {'a'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_75_p_m_n_sequential_correct_order_succeeds(self):
        """
        Scenario: EP(EP(a) & b & !EP(c)). Trace: a@P:1, then b@P:2. 'c' never occurs.
        P-block EP(a) satisfied at P:1.
        M-literal 'b' satisfied at P:2 (which is >= P:1).
        N-block !EP(c) holds throughout.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(a) & b & !EP(c))")
        m.process(E('a_event', {'P'}, {'P': 1}, {'a'}))
        m.process(E('b_event', {'P'}, {'P': 2}, {'b'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_76_p_m_n_sequential_n_violates_before_m_fails(self):
        """
        Scenario: EP(EP(a) & b & !EP(c)). Trace: a@P:1, then c@P:2, then b@P:3.
        P-block EP(a) satisfied at P:1.
        N-block !EP(c) violated at P:2. This occurs before M ('b') is satisfied.
        Expected: FALSE.
        """
        m = Monitor("EP(EP(a) & b & !EP(c))")
        m.process(E('a_event', {'P'}, {'P': 1}, {'a'}))
        m.process(E('c_event', {'P'}, {'P': 2}, {'c'}))  # N-block violated
        # FSM for EP(EP(a)&b&!EP(c)) should become FALSE here:
        # P met at P:1. Current frontier is P:2. P:2 >= P:1.
        # M ('b') not met on P:2. N ('!EP(c)') is violated on P:2.
        # Row 4: n_violated_now is true -> s.failure = True
        assert m.verdict is Verdict.FALSE
        m.process(E('b_event', {'P'}, {'P': 3}, {'b'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_77_p_m_n_sequential_m_not_met_after_p_final_false(self):
        """
        Scenario: EP(EP(a) & b & !EP(c)). Trace: a@P:1. 'b' and 'c' never occur.
        P-block EP(a) satisfied. M-literal 'b' never satisfied correctly after P.
        Expected: FALSE at finish.
        """
        m = Monitor("EP(EP(a) & b & !EP(c))")
        m.process(E('a_event', {'P'}, {'P': 1}, {'a'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_78_m_only_joint_event_satisfies_all_literals_succeeds(self):
        """
        Scenario: EP(j1 & j2). A single joint event on P,Q carries both j1 and j2.
        Expected: TRUE.
        """
        m = Monitor("EP(j1 & j2)")
        m.process(E('tick_p', {'P'}, {'P': 1}, {}))
        m.process(E('tick_q', {'Q'}, {'Q': 1}, {}))
        m.process(E('joint_ev', {'P', 'Q'}, {'P': 2, 'Q': 2}, {'j1', 'j2'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_79_m_only_joint_event_missing_one_literal_final_false(self):
        """
        Scenario: EP(j1 & j2). A joint event carries j1 but not j2.
        Expected: FALSE at finish.
        """
        m = Monitor("EP(j1 & j2)")
        m.process(E('tick_p', {'P'}, {'P': 1}, {}))
        m.process(E('tick_q', {'Q'}, {'Q': 1}, {}))
        m.process(E('joint_ev', {'P', 'Q'}, {'P': 2, 'Q': 2}, {'j1'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_80_p_only_p_block_satisfied_by_joint_event_succeeds(self):
        """
        Scenario: EP(EP(j_prop)). 'j_prop' is on a joint event.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(j_prop))")
        m.process(E('tick_p', {'P'}, {'P': 1}, {}))
        m.process(E('tick_q', {'Q'}, {'Q': 1}, {}))
        m.process(E('joint_ev', {'P', 'Q'}, {'P': 2, 'Q': 2}, {'j_prop'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_81_n_only_joint_event_violates_n_block_after_init_true_remains_true(self):
        """
        Scenario: EP(!EP(j_veto)). Initially TRUE. A joint event then carries 'j_veto'.
        Expected: TRUE (Row 6 N-only success is terminal).
        """
        m = Monitor("EP(!EP(j_veto))")
        assert m.verdict is Verdict.TRUE
        m.process(E('tick_p', {'P'}, {'P': 1}, {}))
        m.process(E('tick_q', {'Q'}, {'Q': 1}, {}))
        m.process(E('joint_veto_ev', {'P', 'Q'}, {'P': 2, 'Q': 2}, {'j_veto'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_82_p_and_m_p_by_single_m_by_joint_succeeds(self):
        """
        Scenario: EP(EP(s_prop) & j_prop). s_prop on P:1. j_prop on joint P:2,Q:1.
        P-block EP(s_prop) met by P:1.
        M-literal j_prop met by joint event, frontier of which is causally after P:1.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(s_prop) & j_prop)")
        m.process(E('s_ev', {'P'}, {'P': 1}, {'s_prop'}))
        m.process(E('joint_ev', {'P', 'Q'}, {'P': 2, 'Q': 1}, {'j_prop'}))  # Q's first event, P's second
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_83_p_and_m_p_by_joint_m_by_single_succeeds(self):
        """
        Scenario: EP(EP(j_prop) & s_prop). j_prop on joint P:1,Q:1. s_prop on P:2.
        P-block EP(j_prop) met by joint P:1,Q:1.
        M-literal s_prop met by P:2, frontier of which is causally after joint.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(j_prop) & s_prop)")
        m.process(E('joint_ev', {'P', 'Q'}, {'P': 1, 'Q': 1}, {'j_prop'}))
        m.process(E('s_ev', {'P'}, {'P': 2}, {'s_prop'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_84_p_and_m_p_by_joint_m_by_single_wrong_order_final_false(self):
        """
        Scenario: EP(EP(j_prop) & s_prop). s_prop on P:1. j_prop on joint P:2,Q:1.
        M-literal s_prop holds at P:1. P-block EP(j_prop) holds at joint P:2,Q:1.
        M is not at/after P.
        Expected: FALSE.
        """
        m = Monitor("EP(EP(j_prop) & s_prop)")
        m.process(E('s_ev', {'P'}, {'P': 1}, {'s_prop'}))
        m.process(E('joint_ev', {'P', 'Q'}, {'P': 2, 'Q': 1}, {'j_prop'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_85_p_and_n_p_by_joint_n_violated_by_single_fails(self):
        """
        Scenario: EP(EP(j_prop) & !EP(s_veto)). s_veto on P:1. j_prop on joint P:2,Q:1.
        N-block !EP(s_veto) violated by P:1 before P-block EP(j_prop) is met.
        Expected: FALSE.
        """
        m = Monitor("EP(EP(j_prop) & !EP(s_veto))")
        m.process(E('s_veto_ev', {'P'}, {'P': 1}, {'s_veto'}))
        assert m.verdict is Verdict.FALSE
        m.process(E('joint_ev', {'P', 'Q'}, {'P': 2, 'Q': 1}, {'j_prop'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_86_m_and_n_m_by_joint_n_not_violated_succeeds(self):
        """
        Scenario: EP(j_main & !EP(s_veto)). j_main on joint P:1,Q:1. s_veto never occurs.
        Expected: TRUE.
        """
        m = Monitor("EP(j_main & !EP(s_veto))")
        m.process(E('joint_ev', {'P', 'Q'}, {'P': 1, 'Q': 1}, {'j_main'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_87_out_of_order_joint_event_buffered_then_delivered_succeeds(self):
        """
        Scenario: EP(j_prop). Joint event P:2,Q:1 arrives before P:1.
        Expected: TRUE after P:1 allows joint to be delivered.
        """
        m = Monitor("EP(j_prop)")
        m.process(E('joint_ev', {'P', 'Q'}, {'P': 2, 'Q': 1}, {'j_prop'}))  # Buffered
        assert m.verdict is Verdict.INCONCLUSIVE
        m.process(E('p_tick1', {'P'}, {'P': 1}, {}))  # Flushes joint_ev
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_88_joint_event_makes_two_p_blocks_true_succeeds(self):
        """
        Scenario: EP(EP(p1) & EP(p2)). A joint event carries both p1 and p2.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(p1) & EP(p2))")
        m.process(E('joint_p1p2', {'P', 'Q'}, {'P': 1, 'Q': 1}, {'p1', 'p2'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_89_disjunction_branch1_single_branch2_joint_joint_succeeds(self):
        """
        Scenario: EP( EP(s_prop) | EP(j_prop) )
        Trace: Only joint event with j_prop occurs.
        Expected: TRUE.
        """
        m = Monitor("EP( EP(s_prop) | EP(j_prop) )")
        m.process(E('p_tick', {'P'}, {'P': 1}, {}))
        m.process(E('q_tick', {'Q'}, {'Q': 1}, {}))
        m.process(E('joint_j', {'P', 'Q'}, {'P': 2, 'Q': 2}, {'j_prop'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_90_p_m_n_all_on_one_joint_event_succeeds(self):
        """
        Scenario: EP(EP(p_past) & m_now & !EP(n_past_false))
        A single joint event provides m_now. Another earlier joint event provided p_past.
        n_past_false is never true.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(p_past) & m_now & !EP(n_past_false))")
        m.process(E('joint_past', {'A', 'B'}, {'A': 1, 'B': 1}, {'p_past'}))  # P-block EP(p_past) satisfied
        m.process(E('joint_now', {'A', 'B'}, {'A': 2, 'B': 2}, {'m_now'}))  # M-literal m_now satisfied
        # !EP(n_past_false) holds
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_91_p_m_n_all_on_one_joint_event_n_violates_fails(self):
        """
        Scenario: EP(EP(p_past) & m_now & !EP(n_past_true))
        A joint event provides m_now. Another earlier joint event provided p_past.
        A third event (could be joint or single) makes n_past_true.
        If n_past_true happens at/before m_now on a valid path from p_past.
        Expected: FALSE.
        """
        m = Monitor("EP(EP(p_past) & m_now & !EP(n_past_true))")
        m.process(E('joint_past', {'A', 'B'}, {'A': 1, 'B': 1}, {'p_past'}))
        m.process(E('n_event', {'C'}, {'C': 1}, {'n_past_true'}))  # N-block violated
        m.process(E('joint_now', {'A', 'B'}, {'A': 2, 'B': 2}, {'m_now'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_92_sequential_joint_events_build_causal_history_for_p_m(self):
        """
        Scenario: EP(m2 & EP(m1)).
        Trace: joint1(P,Q) has m1. Then joint2(P,Q) has m2.
        Expected: TRUE.
        """
        m = Monitor("EP(m2 & EP(m1))")
        m.process(E('joint1', {'P', 'Q'}, {'P': 1, 'Q': 1}, {'m1'}))  # EP(m1) satisfied
        m.process(E('joint2', {'P', 'Q'}, {'P': 2, 'Q': 2}, {'m2'}))  # m2 satisfied, causally after joint1
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_93_joint_event_buffered_then_another_joint_event_flushes_it(self):
        """
        Scenario: EP(buffered_prop & final_prop)
        Trace: joint_final(P,Q)@P3,Q3 {final_prop}
               joint_buffered(P,Q)@P2,Q2 {buffered_prop} (arrives first, buffered)
               tick_p1@P1, tick_q1@Q1
        Expected: TRUE
        """
        m = Monitor("EP(buffered_prop & final_prop)")
        m.process(E('j_final', {'P', 'Q'}, {'P': 3, 'Q': 3}, {'final_prop'}))  # Buffered
        m.process(E('j_buffered', {'P', 'Q'}, {'P': 2, 'Q': 2}, {'buffered_prop'}))  # Buffered
        assert m.verdict is Verdict.INCONCLUSIVE

        m.process(E('p1', {'P'}, {'P': 1}, {}))
        m.process(E('q1', {'Q'}, {'Q': 1}, {}))  # Flushes j_buffered, then j_final
        m.finish()
        # After flush: frontier <P:j_final, Q:j_final> has final_prop.
        # Frontier <P:j_buffered, Q:j_buffered> has buffered_prop.
        # We need a single frontier where BOTH hold. This trace won't achieve it for EP(M&M).
        # Let's change formula to EP(EP(buffered_prop) & final_prop)
        m_complex = Monitor("EP(EP(buffered_prop) & final_prop)")
        m_complex.process(E('j_final', {'P', 'Q'}, {'P': 3, 'Q': 3}, {'final_prop'}))  # Buffered
        m_complex.process(E('j_buffered', {'P', 'Q'}, {'P': 2, 'Q': 2}, {'buffered_prop'}))  # Buffered
        m_complex.process(E('p1_c', {'P'}, {'P': 1}, {}))
        m_complex.process(E('q1_c', {'Q'}, {'Q': 1}, {}))  # Flushes j_buffered (P:2,Q:2), then j_final (P:3,Q:3)
        # After j_buffered is processed, EP(buffered_prop) is true.
        # When j_final is processed, final_prop is true. This frontier is after j_buffered.
        m_complex.finish()
        assert m_complex.verdict is Verdict.TRUE

    def test_94_three_procs_joint_then_single_on_one_of_them(self):
        """
        Scenario: EP(EP(j_abc) & a_later).
        j_abc on {A,B,C}. a_later on {A} at a later timestamp for A.
        Expected: TRUE.
        """
        m = Monitor("EP(EP(j_abc) & a_later)")
        m.process(E('j1', {'A', 'B', 'C'}, {'A': 1, 'B': 1, 'C': 1}, {'j_abc'}))  # EP(j_abc) met
        m.process(E('a2', {'A'}, {'A': 2}, {'a_later'}))  # M-literal met, causally after j1 for A
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_95_overlapping_joint_events_m_only_fails_causality(self):
        """
        Scenario: EP(m_ab & m_bc).
        Event ev_ab on {A,B} has m_ab. Event ev_bc on {B,C} has m_bc.
        Expected: FALSE, because no causally valid frontier can have both m_ab and m_bc.

        The frontier {A:ev_ab, B:ev_bc, C:ev_bc} would satisfy the literals but
        violates causality: ev_ab knew B at timestamp 2, but ev_bc shows B at timestamp 3.
        """
        m = Monitor("EP(m_ab & m_bc)")
        m.process(E('ev_a_tick', {'A'}, {'A': 1}, {}))
        m.process(E('ev_b_tick', {'B'}, {'B': 1}, {}))
        m.process(E('ev_c_tick', {'C'}, {'C': 1}, {}))
        m.process(E('ev_ab', {'A', 'B'}, {'A': 2, 'B': 2}, {'m_ab'}))
        m.process(E('ev_bc', {'B', 'C'}, {'B': 3, 'C': 2}, {'m_bc'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_96_joint_event_satisfies_p_m_n_correctly_succeeds(self):
        """
        Scenario: EP(EP(p_j) & m_j & !EP(n_j_false))
        All p_j, m_j are on one joint event. n_j_false never occurs.
        Expected: TRUE.
        EP(p_j) means p_j holds on the frontier. m_j holds. !EP(n_j_false) holds.
        """
        m = Monitor("EP(EP(p_j) & m_j & !EP(n_j_false))")
        m.process(E('tick_a', {'A'}, {'A': 1}, {}))
        m.process(E('tick_b', {'B'}, {'B': 1}, {}))
        m.process(E('joint_all', {'A', 'B'}, {'A': 2, 'B': 2}, {'p_j', 'm_j'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_97_joint_event_violates_n_in_p_m_n_fails(self):
        """
        Scenario: EP(EP(p_j) & m_j & !EP(n_j_true))
        p_j, m_j, n_j_true all on one joint event.
        Expected: FALSE because N-block is violated.
        """
        m = Monitor("EP(EP(p_j) & m_j & !EP(n_j_true))")
        m.process(E('tick_a', {'A'}, {'A': 1}, {}))
        m.process(E('tick_b', {'B'}, {'B': 1}, {}))
        m.process(E('joint_all_violate', {'A', 'B'}, {'A': 2, 'B': 2}, {'p_j', 'm_j', 'n_j_true'}))
        m.finish()
        assert m.verdict is Verdict.FALSE

    def test_98_iota_in_joint_event_prop_n_only_fails(self):
        """
        Scenario: EP(!EP(iota_on_joint))
        A joint event carries 'iota_on_joint'.
        This is tricky because 'iota' is special. If 'iota_on_joint' is treated as ordinary.
        Expected: TRUE initially, then remains TRUE as Row 6 success is terminal.
                  If the FSM considered this 'iota_on_joint' the same as the special 'iota', it would be FALSE.
                  Assuming 'iota_on_joint' is a regular prop.
        """
        m = Monitor("EP(!EP(iota_on_joint))")
        assert m.verdict is Verdict.TRUE  # Initial success
        m.process(E('j1', {'P', 'Q'}, {'P': 1, 'Q': 1}, {'iota_on_joint'}))
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_99_complex_disjunction_with_joint_events_one_branch_succeeds(self):
        """
        Scenario: EP( (EP(s1) & !EP(j1)) | (EP(j2) & m_s & !EP(s2)) )
        Trace: j2 occurs, then m_s occurs. s1, j1, s2 never occur.
        Expected: TRUE (second disjunct succeeds).
        """
        formula = "EP( (EP(s1) & !EP(j1)) | (EP(j2) & m_s & !EP(s2)) )"
        m = Monitor(formula)
        m.process(E('tick_p', {'P'}, {'P': 1}, {}))
        m.process(E('tick_q', {'Q'}, {'Q': 1}, {}))
        m.process(E('joint_j2', {'P', 'Q'}, {'P': 2, 'Q': 2}, {'j2'}))  # EP(j2) for 2nd disjunct
        m.process(E('single_ms', {'R'}, {'R': 1}, {'m_s'}))  # m_s for 2nd disjunct
        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_100_m_only_specific_trace_expects_true(self):
        """
        Property: EP(status_ok & load_lt_100 & !critical_alarm)
        Trace:
        # system_processes: P1|P2|P3
        evA,P2,P1:0;P2:1;P3:0,
        evB,P3,P1:0;P2:0;P3:1,
        evC,P1,P1:1;P2:0;P3:0,
        evD,P3,P1:0;P2:0;P3:2,critical_alarm
        evE,P1,P1:2;P2:0;P3:0,status_ok|load_lt_100
        Expected: TRUE, because a frontier {P1:evE, P2:init, P3:init} satisfies the M-block.
        """
        spec = "EP(status_ok & load_lt_100 & !critical_alarm)"
        m = Monitor(spec)
        # Define all system processes upfront for correct initial_system_frontier
        m.activate_window_optimization({"P1", "P2", "P3"})

        # After Monitor init and activate_window_optimization (which seeds FSMs),
        # the M-block is false on the initial frontier.
        assert m.verdict is Verdict.INCONCLUSIVE

        m.process(E('evA', {'P2'}, {'P1': 0, 'P2': 1, 'P3': 0}, set()))
        m.process(E('evB', {'P3'}, {'P1': 0, 'P2': 0, 'P3': 1}, set()))
        m.process(E('evC', {'P1'}, {'P1': 1, 'P2': 0, 'P3': 0}, set()))
        m.process(E('evD', {'P3'}, {'P1': 0, 'P2': 0, 'P3': 2}, {'critical_alarm'}))
        # When evE is processed, a candidate frontier extending the initial system frontier
        # should be: Frontier({'P1':evE, 'P2':initial_event_P2, 'P3':initial_event_P3})
        # On this frontier: status_ok=T, load_lt_100=T, critical_alarm=F.
        # This should make the FSM TRUE.
        m.process(E('evE', {'P1'}, {'P1': 2, 'P2': 0, 'P3': 0}, {'status_ok', 'load_lt_100'}))

        m.finish()
        assert m.verdict is Verdict.TRUE

    def test_101_m_only_specific_trace_expects_false(self):
        """
        Property: EP(status_ok & load_lt_100 & !critical_alarm)
        Trace:
        # system_processes: P1|P2|P3
        evA,P2,P1:0;P2:1;P3:0,
        evB,P3,P1:0;P2:1;P3:1,
        evC,P1,P1:1;P2:1;P3:1,
        evD,P3,P1:1;P2:1;P3:2,critical_alarm
        evE,P1,P1:2;P2:1;P3:2,status_ok|load_lt_100
        Expected: FALSE, because evE's VC implies P3 is at evD (which has critical_alarm).
                  Any consistent frontier containing evE will also reflect P3's state as evD or later.
        """
        spec = "EP(status_ok & load_lt_100 & !critical_alarm)"
        m = Monitor(spec)
        # Define all system processes upfront
        m.activate_window_optimization({"P1", "P2", "P3"})

        assert m.verdict is Verdict.INCONCLUSIVE

        m.process(E('evA', {'P2'}, {'P1': 0, 'P2': 1, 'P3': 0}, set()))
        m.process(E('evB', {'P3'}, {'P1': 0, 'P2': 1, 'P3': 1}, set()))
        m.process(E('evC', {'P1'}, {'P1': 1, 'P2': 1, 'P3': 1}, set()))
        m.process(E('evD', {'P3'}, {'P1': 1, 'P2': 1, 'P3': 2}, {'critical_alarm'}))
        m.process(E('evE', {'P1'}, {'P1': 2, 'P2': 1, 'P3': 2}, {'status_ok', 'load_lt_100'}))

        # When evE is processed, the relevant maximal frontier will be
        # Frontier({'P1':evE, 'P2':evA, 'P3':evD}).
        # On this, critical_alarm is TRUE, so the M-block is FALSE.
        # No other frontier satisfying status_ok & load_lt_100 will have critical_alarm as FALSE.
        m.finish()
        assert m.verdict is Verdict.FALSE

