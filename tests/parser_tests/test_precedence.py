# tests/parser_test/test_precedence.py


"""
Ensures the parser correctly handles operator precedence and associativity.

This test suite verifies that the parser correctly interprets expressions
according to the specified operator precedence rules: NOT > AND > OR. It also
confirms that parentheses correctly override this natural order and that
chained operators are associated correctly (e.g., left-associative for AND/OR).

Each test case provides an input string and a manually constructed, expected
Abstract Syntax Tree (AST). The test succeeds if the parser's output AST
is structurally identical to the expected one.
"""
import pytest
from parser import parse
from parser.ast_nodes import And, Or, Not, Literal, EP

# A comprehensive list of test cases for operator precedence.
# Each entry is a tuple: (source_string, expected_ast_object)
TEST_CASES = [
    # --- Basic Precedence (AND vs OR) ---
    # `&` has higher precedence than `|`. `b & c` should be grouped first.
    ("a | b & c", Or(Literal("a"), And(Literal("b"), Literal("c")))),
    # `a & b` is grouped first.
    ("a & b | c", Or(And(Literal("a"), Literal("b")), Literal("c"))),
    # A chain of `|` and `&` operators, respecting precedence.
    ("a | b & c | d", Or(Or(Literal("a"), And(Literal("b"), Literal("c"))), Literal("d"))),

    # --- Unary NOT Precedence ---
    # `!` has the highest precedence, applying only to `a`.
    ("!a & b", And(Not(Literal("a")), Literal("b"))),
    # `!` applies to `a`, then `&` is evaluated, then `|`.
    ("!a & b | c", Or(And(Not(Literal("a")), Literal("b")), Literal("c"))),
    # `!` applies to `b` before `&`, then `|` is evaluated.
    ("a | !b & c", Or(Literal("a"), And(Not(Literal("b")), Literal("c")))),
    # `!` applies to both `a` and `c` before their respective `&` and `|`.
    ("!a | b & !c", Or(Not(Literal("a")), And(Literal("b"), Not(Literal("c"))))),
    # A combination of multiple `!` and `&` operators before `|`.
    ("!a & !b | !c", Or(And(Not(Literal("a")), Not(Literal("b"))), Not(Literal("c")))),

    # --- Parentheses Overriding Precedence ---
    # Parentheses force `b | c` to be evaluated before `&`.
    ("a & (b | c)", And(Literal("a"), Or(Literal("b"), Literal("c")))),
    # Parentheses force `a | b` to be evaluated before `&`.
    (" (a | b) & c", And(Or(Literal("a"), Literal("b")), Literal("c"))),
    # `!` applies to the entire result of the parenthesized group `a | b`.
    ("!(a | b) & c", And(Not(Or(Literal("a"), Literal("b"))), Literal("c"))),
    # Deeply nested parentheses to override multiple precedence rules.
    ("a & (b | (c & !d))", And(Literal("a"), Or(Literal("b"), And(Literal("c"), Not(Literal("d")))))),

    # --- Associativity and Chaining ---
    # Chained `&` operators should be left-associative: `(a & b) & c`.
    ("a & b & c", And(And(Literal("a"), Literal("b")), Literal("c"))),
    # Chained `|` operators should be left-associative: `(a | b) | c`.
    ("a | b | c", Or(Or(Literal("a"), Literal("b")), Literal("c"))),
    # Unary `!` is effectively right-associative: `!(!(!p))`.
    ("!!!p", Not(Not(Not(Literal("p"))))),
    # A long chain of mixed operators to test associativity and precedence together.
    ("a & b | c & d | e", Or(Or(And(Literal("a"), Literal("b")), And(Literal("c"), Literal("d"))), Literal("e"))),

    # --- `EP` Operator Precedence ---
    # `!` has higher precedence than `EP` via grammar rules.
    ("!EP(p)", Not(EP(Literal("p")))),
    # `EP` binds to its argument before the `&` operator.
    ("EP(p) & q", And(EP(Literal("p")), Literal("q"))),
    # Precedence rules apply correctly inside an `EP`'s argument.
    ("EP(p | q & r)", EP(Or(Literal("p"), And(Literal("q"), Literal("r"))))),
    # Parentheses inside an `EP` override internal precedence.
    ("EP((p | q) & r)", EP(And(Or(Literal("p"), Literal("q")), Literal("r")))),
    # `EP` as part of a larger group.
    ("(EP(p) | q) & r", And(Or(EP(Literal("p")), Literal("q")), Literal("r"))),

    # --- Boolean Constants ---
    # Tests that constants are treated like any other literal in terms of precedence.
    ("true | false & true", Or(Literal("true"), And(Literal("false"), Literal("true")))),
    # `!` applies to `true` before `&` is evaluated.
    ("!true & false", And(Not(Literal("true")), Literal("false"))),
    # Precedence is respected inside the `EP` argument.
    ("EP(true & p | false)", EP(Or(And(Literal("true"), Literal("p")), Literal("false")))),
]


@pytest.mark.parametrize("src, expected", TEST_CASES)
def test_operator_precedence(src, expected, capsys):
    """
    Verify that the parser builds an AST that correctly respects operator
    precedence (`! > & > |`) and grouping via parentheses.
    """
    actual = parse(src)

    print(f"\nInput string : {src}")
    print(f"Actual AST   : {actual}")
    print(f"Expected AST : {expected}")

    assert actual == expected, "The parsed AST structure does not match the expected structure."
    _ = capsys.readouterr()