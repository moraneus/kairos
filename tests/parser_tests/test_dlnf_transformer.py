# tests/parser_test/test_dlnf_transformer.py

"""
Verifies the DLNF (Disjunctive Literal Normal Form) transformation logic. [cite: 1]

This test suite ensures that the DLNF transformer correctly converts any given
PBTL formula into its corresponding Disjunctive Normal Form. It validates three
key properties:

1.  **Correctness**: The transformed Abstract Syntax Tree (AST) must be
    structurally identical to the expected output. This is checked by comparing
    the parsed ASTs, which is more robust than simple string comparison. [cite: 1]
2.  **DLNF Structure**: No disjunction ('|') should appear inside the scope
    of an 'EP' operator in the final output. [cite: 1]
3.  **Idempotence**: Applying the transformation a second time to an already
    transformed formula should result in no further changes. [cite: 1]
"""
import re
import pytest
from parser import parse, parse_and_dlnf

# A regular expression to find any '|' character within an EP() block.
# This serves as a quick check for violations of the DLNF structure. [cite: 1]
OR_IN_EP = re.compile(r"EP\([^()]*\|")

# A list of test cases, where each entry is a tuple containing:
# (input_string, expected_dlnf_string) [cite: 1]
TESTS = [
    # --- Basic Distribution Scenarios ---
    # Verifies the fundamental rule: EP(A | B) -> EP(A) | EP(B). [cite: 1]
    ("EP(p | q)", "(EP(p) | EP(q))"),
    # An EP wrapping a conjunction should remain unchanged. [cite: 1]
    ("EP(p & q)", "EP((p & q))"),
    # Ensures distribution works correctly on a left-associative OR chain. [cite: 1]
    ("EP((p | q) | r)", "((EP(p) | EP(q)) | EP(r))"),
    # Checks distribution with a mixed AND/OR operand. [cite: 1]
    ("EP((p & q) | r)", "(EP((p & q)) | EP(r))"),
    # A top-level OR should be preserved after inner transformations. [cite: 1]
    ("EP(p | q) | EP(r)", "((EP(p) | EP(q)) | EP(r))"),

    # --- DNF and Distribution Scenarios ---
    # Tests DNF conversion for an AND of two ORs inside an EP. [cite: 1]
    ("EP((p | q) & (r | s))", "(((EP((p & r)) | EP((p & s))) | EP((q & r))) | EP((q & s)))"),
    # A top-level AND of two transformed expressions must be converted to DNF. [cite: 1]
    ("EP(a|b) & EP(c|d)", "(((EP(a) & EP(c)) | (EP(a) & EP(d))) | (EP(b) & EP(c))) | (EP(b) & EP(d))"),
    # Tests distribution over a long, un-parenthesized (and thus left-associative) OR chain. [cite: 1]
    ("EP(a | b | c | d)", "(((EP(a) | EP(b)) | EP(c)) | EP(d))"),
    # Tests distribution over a complex, right-associative chain of ANDs and ORs. [cite: 1]
    ("EP(a & (b | (c & (d | e))))", "((EP((a & b)) | EP(((a & c) & d))) | EP(((a & c) & e)))"),

    # --- Negation and De Morgan's Law Scenarios ---
    # Tests De Morgan's Law: !(A & B) becomes !A | !B, which is then distributed. [cite: 1]
    ("EP(!(p & q))", "(EP(!p) | EP(!q))"),
    # A double negation (involution) should be simplified before distribution. [cite: 1]
    ("EP(!!(p | q))", "(EP(p) | EP(q))"),
    # A negated EP should be treated as an atomic unit and not transformed further. [cite: 1]
    ("EP(!(EP(p & q)))", "EP(!(EP((p & q))))"),
    # Tests distribution on a formula containing a negated AND: !(q & r) -> !q | !r. [cite: 1]
    ("EP(p | !(q & r))", "((EP(p) | EP(!q)) | EP(!r))"),
    # A more complex application of De Morgan's Law with an existing negation. [cite: 1]
    ("EP(!((p | !q) & r))", "(EP((!p & q)) | EP(!r))"),

    # --- Nested and Complex Scenarios ---
    # Verifies recursive distribution with a nested EP expression. [cite: 1]
    ("EP(p | EP(q | r))", "((EP(p) | EP(EP(q))) | EP(EP(r)))"),
    # Verifies a deeply nested structure with mixed operators at multiple levels. [cite: 1]
    ("EP(a | (b & EP(c | (d & EP(e | f)))))", "(((EP(a) | EP((b & EP(c)))) | EP((b & EP((d & EP(e)))))) | EP((b & EP((d & EP(f))))))"),
    # Verifies recursive application of De Morgan's Law on a complex, nested negation. [cite: 1]
    ("EP(!(p & (q | EP(r | s))))", "(EP(!p) | EP(((!q & !EP(r)) & !EP(s))))"),
]


@pytest.mark.parametrize("src, expected_str", TESTS)
def test_dlnf_transformation(src, expected_str, capsys):
    """
    For each test case, validates the DLNF transformation for correctness,
    proper structure, and idempotence. [cite: 1]
    """
    # Phase 1: Initial Transformation and Verification [cite: 1]
    dlnf_ast = parse_and_dlnf(src)
    dlnf_str = str(dlnf_ast)
    expected_ast = parse(expected_str)

    print(f"\nInput           : {src}")
    print(f"Actual Result   : {dlnf_str}")
    print(f"Expected Result : {expected_str}")

    assert not OR_IN_EP.search(dlnf_str), "Found '|' inside an EP() expression"
    assert dlnf_ast == expected_ast, "Transformed AST does not match expected structure"

    # Phase 2: Idempotence Verification [cite: 1]
    idempotent_ast = parse_and_dlnf(dlnf_str)
    print(f"Idempotent Pass : {idempotent_ast}")
    assert idempotent_ast == dlnf_ast, "Transformation is not idempotent"
    _ = capsys.readouterr()