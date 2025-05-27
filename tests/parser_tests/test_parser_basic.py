# tests/parser_test/test_parse_basic.py


"""
Tests the round-trip integrity of the parser and AST string representation.

This test suite verifies that for any valid formula, the following process
preserves the structural integrity of the Abstract Syntax Tree (AST):

1.  Parse a source string into an initial AST (`ast1`).
2.  Convert `ast1` back into its string representation (`str(ast1)`).
3.  Parse the generated string into a second AST (`ast2`).
4.  Confirm that `ast1` and `ast2` are structurally identical.

This process guarantees that the `__str__` methods on the AST nodes produce
syntactically correct and unambiguous output that can be reliably re-parsed.
"""
import pytest
from parser import parse

# A comprehensive list of valid PBTL formulas for round-trip testing.
# The list covers basic syntax, operator precedence, nesting, and edge cases.
VALID_CASES = [
    # --- Basic Literals and Operators ---
    "p",
    "!q",
    "p & q",
    "p | r",
    "EP(s)",

    # --- Precedence and Associativity ---
    "p & q | r",                  # AND has higher precedence than OR.
    "p | q & r",                  # Confirms AND is evaluated before OR.
    "a & b & c",                  # Ensures AND is left-associative.
    "a | b | c",                  # Ensures OR is left-associative.
    "!!!p",                       # Verifies multiple unary NOT operators.

    # --- Parentheses and Grouping ---
    "p & (q | r)",                # Parentheses override default precedence.
    "!(p & q)",                   # Negation of a grouped expression.
    "((p))",                      # Redundant parentheses are preserved by the parser.

    # --- Temporal Operator (`EP`) Combinations ---
    "EP(p & q)",                  # Conjunction inside EP.
    "!EP(p)",                     # Negation of a temporal expression.
    "EP(p) & q",                  # Temporal expression as part of a conjunction.
    "EP(EP(p))",                  # Nested temporal operators.
    "EP(p | !q)",                 # Negation within a temporal expression's operand.
    "EP(p) | EP(q)",              # Disjunction of two temporal expressions.

    # --- Complex Nested Expressions ---
    "!((p | q) & (r | s))",        # A complex negated expression with multiple groups.
    "EP(p & (q | (r & !s)))",      # Deeply nested logical operators inside a temporal one.
    "a & (b | (c & (d | (e & f))))", # Very deep right-associative nesting.

    # --- Boolean Constants ---
    "true",                       # The 'true' literal.
    "!false",                     # The negated 'false' literal.
    "(p | true) & !false",        # Formulas combining literals and boolean constants.

    # --- Whitespace and Formatting ---
    "  p\n& \tq  ",                # Should parse correctly despite varied whitespace.
]


@pytest.mark.parametrize("src", VALID_CASES)
def test_ast_roundtrip_preserves_structure(src, capsys):
    """
    Ensures that for any valid formula string, parsing it, converting the
    resulting AST to a string, and parsing it again yields an identical AST.
    """
    # 1. First parse from the original source string.
    ast1 = parse(src)

    # 2. Convert the resulting AST back into its canonical string representation.
    stringified_ast = str(ast1)

    # 3. Parse the generated string to create a second AST.
    ast2 = parse(stringified_ast)

    # Print diagnostic information for clarity, especially when running with `pytest -s`.
    print(f"\nOriginal source : {src!r}")
    print(f"Stringified AST : {stringified_ast!r}")
    print(f"Round-trip AST  : {ast2}")

    # The two ASTs must be structurally identical for the test to pass.
    assert ast1 == ast2, "AST structure changed after stringifying and re-parsing"
    _ = capsys.readouterr()  # Clear buffered output so pytest shows it correctly on failure.