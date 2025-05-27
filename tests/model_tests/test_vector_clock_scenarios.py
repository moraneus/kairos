# test/model_tests/test_vector_clock_model_scenarios.py

"""VectorClock – happens-before comparisons and helper invariants."""

import pytest
from model.vector_clock import VectorClock as VC


def test_rich_comparison_operators():
    v1 = VC({'P': 1})
    v2 = VC({'P': 2, 'Q': 0})  # v2 is greater because P:2 > P:1 and Q:0 >= (missing Q in v1, treated as 0)
    assert v1 < v2
    assert v1 <= v2
    assert not (v1 > v2)
    assert not (v1 >= v2)
    assert v1 != v2


def test_incomparability_concurrent():
    vP = VC({'P': 1})
    vQ = VC({'Q': 1})
    assert vP.concurrent(vQ)
    assert not (vP < vQ)
    assert not (vP <= vQ)  # For <= to be true, all components of self must be <= other's
    assert not (vQ < vP)
    assert not (vQ <= vP)


def test_leq_matches_dunder():
    v1 = VC({'P': 1})
    v2 = VC({'P': 1, 'Q': 3})
    assert v1.leq(v2) == (v1 <= v2)  # True
    assert v2.leq(v1) == (v2 <= v1)  # False


def test_equality_exact_dict():
    vA = VC({'P': 1})
    vB = VC({'P': 1, 'Q': 0})
    assert vA != vB


def test_hash_stability():
    v1 = VC({'P': 3, 'Q': 4})
    v2 = VC({'Q': 4, 'P': 3})
    assert hash(v1) == hash(v2)
    assert v1 == v2


def test_set_membership():
    s = {VC({'P': 1})}
    assert VC({'P': 1}) in s
    assert VC({'P': 2}) not in s
    assert VC({'P': 1, 'Q': 0}) not in s  # Different clock


def test_increment_and_compare_strict_less_than():
    v1 = VC({'P': 1})
    v2 = VC({'P': 2})
    assert v1 < v2


def test_join_commutative_idempotent():
    v1 = VC({'P': 2})
    v2 = VC({'P': 1, 'Q': 3})
    j1 = v1.join(v2)
    j2 = v2.join(v1)
    expected_join = VC({'P': 2, 'Q': 3})
    assert j1 == expected_join
    assert j2 == expected_join
    assert j1.join(j1) == j1  # Idempotent


# --- New Comprehensive Tests ---

def test_equality_empty_clocks():
    v1 = VC({})
    v2 = VC({})
    assert v1 == v2
    assert hash(v1) == hash(v2)


def test_inequality_one_empty_one_not():
    v1 = VC({})
    v2 = VC({'P': 1})
    assert v1 != v2


def test_leq_reflexive():
    v1 = VC({'P': 1, 'Q': 2})
    assert v1.leq(v1)
    assert v1 <= v1


def test_leq_transitive():
    v1 = VC({'P': 1, 'Q': 1})
    v2 = VC({'P': 1, 'Q': 2, 'R': 1})
    v3 = VC({'P': 2, 'Q': 2, 'R': 1})
    assert v1 <= v2
    assert v2 <= v3
    assert v1 <= v3


def test_lt_transitive():
    v1 = VC({'P': 1})
    v2 = VC({'P': 2})  # v1 < v2
    v3 = VC({'P': 3})  # v2 < v3
    assert v1 < v2
    assert v2 < v3
    assert v1 < v3


def test_lt_irreflexive():
    v1 = VC({'P': 1, 'Q': 2})
    assert not (v1 < v1)


def test_lt_asymmetric():
    v1 = VC({'P': 1})
    v2 = VC({'P': 2})
    assert v1 < v2
    assert not (v2 < v1)


def test_concurrent_different_processes_different_times():
    v1 = VC({'P': 3})
    v2 = VC({'Q': 5})
    assert v1.concurrent(v2)


def test_concurrent_one_knows_more_on_one_less_on_another():
    v1 = VC({'P': 2, 'Q': 1})
    v2 = VC({'P': 1, 'Q': 2})
    assert v1.concurrent(v2)


def test_not_concurrent_if_leq():
    v1 = VC({'P': 1, 'Q': 1})
    v2 = VC({'P': 1, 'Q': 2})  # v1 <= v2
    assert not v1.concurrent(v2)


def test_join_with_empty_clock():
    v1 = VC({'P': 1, 'Q': 2})
    v_empty = VC({})
    assert v1.join(v_empty) == v1
    assert v_empty.join(v1) == v1


def test_join_no_common_processes():
    v1 = VC({'P': 1})
    v2 = VC({'Q': 2})
    assert v1.join(v2) == VC({'P': 1, 'Q': 2})


def test_join_partial_overlap_processes():
    v1 = VC({'P': 1, 'Q': 2})
    v2 = VC({'Q': 1, 'R': 3})
    assert v1.join(v2) == VC({'P': 1, 'Q': 2, 'R': 3})


def test_join_one_subsumes_another():
    v1 = VC({'P': 1, 'Q': 1})
    v2 = VC({'P': 2, 'Q': 2})  # v1 < v2
    assert v1.join(v2) == v2
    assert v2.join(v1) == v2


def test_join_three_way_associativity_like():
    v1 = VC({'P': 1})
    v2 = VC({'Q': 1})
    v3 = VC({'R': 1})
    join_12_then_3 = (v1.join(v2)).join(v3)
    join_23_then_1 = v1.join(v2.join(v3))
    expected = VC({'P': 1, 'Q': 1, 'R': 1})
    assert join_12_then_3 == expected
    assert join_23_then_1 == expected


def test_comparison_with_missing_keys_one_way_leq():
    v1 = VC({'P': 1})
    v2 = VC({'P': 1, 'Q': 1})  # v1 <= v2 (Q missing in v1 is like Q:0)
    assert v1 <= v2
    assert not (v2 <= v1)  # Fails because v2 has Q:1 > (missing Q in v1, treated as 0)
    # Correction: Fails because v1 has P:1 == v2's P:1, but v1 is "smaller" due to missing Q.
    # For v2 <= v1 to be true, all of v2's components must be <= v1's.
    # v2.Q (1) > v1.Q (0 implicitly). So v2 is not <= v1.


def test_comparison_with_missing_keys_concurrent():
    v1 = VC({'P': 2})
    v2 = VC({'P': 1, 'Q': 1})  # P:2 > P:1, but v1 misses Q where v2 has Q:1
    assert v1.concurrent(v2)


def test_copy_method():
    v1 = VC({'P': 1, 'Q': 2})
    v_copy = v1.copy()
    assert v_copy == v1
    assert v_copy is not v1  # Should be a new object
    assert v_copy.clock is not v1.clock  # Inner dict should also be a copy


def test_str_representation_empty():
    v = VC({})
    assert str(v) == "[]"


def test_str_representation_single_entry():
    v = VC({'P': 5})
    assert str(v) == "[P:5]"


def test_str_representation_multiple_entries_sorted():
    v = VC({'Q': 2, 'P': 1, 'R': 3})
    assert str(v) == "[P:1, Q:2, R:3]"  # Relies on sorted output


def test_greater_than_operator():
    v_smaller = VC({'A': 1, 'B': 2})
    v_larger = VC({'A': 1, 'B': 3})  # B is greater
    assert v_larger > v_smaller
    assert not (v_smaller > v_larger)


def test_greater_than_or_equal_operator():
    v1 = VC({'A': 1, 'B': 2})
    v2 = VC({'A': 1, 'B': 3})
    v3 = VC({'A': 1, 'B': 2})
    assert v2 >= v1
    assert v1 >= v3
    assert v2 >= v3
    assert not (v1 >= v2)


def test_complex_scenario_chain_and_fork():
    # P0 -> P1 -> P2_sync_with_Q1
    # Q0 -> Q1_sync_with_P2
    p0 = VC({})
    p1 = VC({'P': 1})  # P's internal event
    q0 = VC({})
    q1 = VC({'Q': 1})  # Q's internal event

    # Sync event between P and Q after their respective p1 and q1
    vc_p_before_sync = p1.copy()
    vc_q_before_sync = q1.copy()

    # P's clock for sync event
    vc_p_at_sync = VC({**vc_p_before_sync.clock, 'P': vc_p_before_sync.clock.get('P', 0) + 1})
    # Q's clock for sync event
    vc_q_at_sync = VC({**vc_q_before_sync.clock, 'Q': vc_q_before_sync.clock.get('Q', 0) + 1})

    sync_event_vc = vc_p_at_sync.join(vc_q_at_sync)
    # Expected: P increments to 2 (from 1), Q increments to 2 (from 1)
    # Message from P carries P:2, Q:0 (if P only knew its own state)
    # Message from Q carries P:0, Q:2
    # Join of {P:2, Q:0} and {P:0, Q:2} is {P:2, Q:2}
    # However, if p1 saw q1 (or vice-versa before sync), it's different.
    # Let's assume p1 and q1 are independent.
    # P has event, its clock is {P:1}
    # Q has event, its clock is {Q:1}
    # P sends message: P increments clock to {P:2}, message carries {P:2}
    # Q sends message: Q increments clock to {Q:2}, message carries {Q:2}
    # Let's model a shared event 'sync' where both participate:
    # P's state before sync: {P:1}
    # Q's state before sync: {Q:1}
    # At sync event:
    # P increments its P component: {P:2}
    # Q increments its Q component: {Q:2}
    # Merged VC for sync event: max({P:2, Q:0 initially for P}, {P:0 initially for Q, Q:2})
    # Simplified: If P's clock becomes {P:x} and Q's {Q:y} for the event
    # VCs for P and Q participating in shared event 'ev_shared':
    # clock_P_for_ev_shared = {'P': current_P_clock['P']+1, **other_components_from_P}
    # clock_Q_for_ev_shared = {'Q': current_Q_clock['Q']+1, **other_components_from_Q}
    # ev_shared_vc = clock_P_for_ev_shared.join(clock_Q_for_ev_shared)

    # Simpler: event P_ev1 ({P:1}), Q_ev1 ({Q:1})
    # Shared event SQ_ev2:
    # P's VC before SQ_ev2: {P:1}
    # Q's VC before SQ_ev2: {Q:1}
    # For SQ_ev2: P does P_clock_val+1 -> P:2. Q does Q_clock_val+1 -> Q:2.
    # VC of SQ_ev2 is join of P's state {P:2} and Q's state {Q:2} (assuming no prior cross-knowledge)
    # So, VC of SQ_ev2 is {P:2, Q:2}
    vc_p_ev1 = VC({'P': 1})
    vc_q_ev1 = VC({'Q': 1})
    vc_sq_ev2 = VC({'P': 2, 'Q': 2})  # Assuming it's the direct successor on both P and Q after their first events

    assert vc_p_ev1 < vc_sq_ev2
    assert vc_q_ev1 < vc_sq_ev2

    # Event P_ev3 after sync on P
    vc_p_ev3 = VC({'P': 3, 'Q': 2})  # P had another event, its P clock is 3, it knows Q was at 2 from sync
    assert vc_sq_ev2 < vc_p_ev3
    assert vc_p_ev1 < vc_p_ev3


def test_join_with_itself_is_itself():
    v1 = VC({'X': 10, 'Y': 5})
    assert v1.join(v1) == v1


def test_deep_equality_check():
    # Ensures that even if internal dicts are different objects but same content, VCs are equal
    d1 = {'P': 1, 'Q': 2}
    d2 = {'P': 1, 'Q': 2}
    v1 = VC(d1)
    v2 = VC(d2)
    assert d1 is not d2  # Ensure dicts are different objects
    assert v1 == v2
    assert hash(v1) == hash(v2)
