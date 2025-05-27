# test/model_tests/test_vector_clock_model_scenarios.py


"""VectorClock – happens-before comparisons and helper invariants."""

from model.vector_clock import VectorClock as VC


def _hdr(title: str, *msgs):
    print(f"\n─ {title} ─")
    for m in msgs:
        print(m)


# ─────────────────────────── new comparison tests ───────────────────────────

def test_rich_comparison_operators(capsys):
    v1 = VC({'P': 1})
    v2 = VC({'P': 2, 'Q': 0})
    _hdr("Rich comparison", f"v1={v1}", f"v2={v2}")
    print("Actual  (<,<=,>,>=,==):", v1 < v2, v1 <= v2, v1 > v2, v1 >= v2, v1 == v2)
    print("Expected              :", True, True, False, False, False)
    assert (v1 < v2) and (v1 <= v2) and not (v1 > v2) and not (v1 >= v2) and v1 != v2


def test_incomparability(capsys):
    vP = VC({'P': 1})
    vQ = VC({'Q': 1})
    _hdr("Concurrent clocks", f"vP={vP}", f"vQ={vQ}")
    print("Actual concurrent():", vP.concurrent(vQ))
    assert vP.concurrent(vQ)
    assert not (vP < vQ or vQ < vP)


def test_leq_matches_dunder(capsys):
    v1 = VC({'P': 1})
    v2 = VC({'P': 1, 'Q': 3})
    _hdr("leq vs. <=", f"v1={v1}", f"v2={v2}")
    assert v1.leq(v2) == (v1 <= v2)
    assert v2.leq(v1) == (v2 <= v1)


def test_equality_exact_dict(capsys):
    vA = VC({'P': 1})
    vB = VC({'P': 1, 'Q': 0})  # extra zero component ≠
    _hdr("Exact == semantics", f"vA={vA}", f"vB={vB}")
    print("Actual (==):", vA == vB)
    assert vA != vB


def test_hash_stability(capsys):
    v1 = VC({'P': 3, 'Q': 4})
    v2 = VC({'Q': 4, 'P': 3})  # same mapping, different order
    assert hash(v1) == hash(v2) and v1 == v2


def test_set_membership(capsys):
    s = {VC({'P': 1})}
    assert VC({'P': 1}) in s
    assert VC({'P': 2}) not in s


# ─────────────────────────── existing “basic” tests ─────────────────────────

def test_increment_and_compare(capsys):
    v1 = VC({'P': 1})
    v2 = VC({'P': 2})
    _hdr("HB simple", f"v1={v1}", f"v2={v2}")
    assert v1 < v2


def test_join_commutative_idempotent(capsys):
    v1 = VC({'P': 2})
    v2 = VC({'P': 1, 'Q': 3})
    j1, j2 = v1.join(v2), v2.join(v1)
    _hdr("Join", f"j1={j1}", f"j2={j2}")
    assert j1 == j2 and j1.join(j1) == j1
