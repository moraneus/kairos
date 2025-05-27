# tests/parser_test/test_parse_errors.py

"""
Tests the parser's general syntax handling, round-trip integrity,
and error reporting for both the basic parser and the DLNF transformer.

This test suite is crucial for ensuring the parser is both robust and correct.
It is divided into two main sections:

1.  **Round-Trip Integrity**: Verifies that syntactically correct formulas can be
    parsed into an Abstract Syntax Tree (AST), then converted back into a
    string, and finally parsed again to yield an identical AST. This ensures
    the string representations of the AST nodes are valid and unambiguous.

2.  **Error Handling**: Verifies that any syntactically invalid input string
    correctly and reliably raises a `ParseError`. This is tested against both
    the simple `parse()` function and the `parse_and_dlnf()` entrypoint.
"""
import pytest
from parser import parse, parse_and_dlnf, ParseError

# A list of valid, representative PBTL formulas for round-trip testing.
# This list includes simple cases, all operators, nesting, and edge cases.
VALID_SYNTAX_CASES = [
    # --- Basic Cases ---
    "p",                           # Simplest case: a single literal.
    "!q",                          # Simple negation.
    "(p & q)",                     # Simple conjunction.
    "EP(r)",                       # Simple temporal operator.
    "(EP(p) | EP(!q))",            # Disjunction of temporal expressions.

    # --- Complex Nesting and Precedence ---
    "EP((p & q) | !r)",            # Mixed operators inside an EP.
    "!(p | EP(q))",                # Negation of a compound expression.
    "EP(EP(EP(p)))",               # Deeply nested temporal operators.
    "(!p | !q)",                   # Disjunction of negations.
    "(p & (q | (r & (s | t))))",   # Deeply nested logical operators.

    # --- Edge Cases ---
    "EP(true)",                    # Using a boolean constant.
    "  (p | q)  ",                 # Handling of leading/trailing whitespace.
    "EP(id_with_EP_in_it)",        # An identifier containing a keyword substring.
    "(a | b) & (c | !d)",          # Combination of multiple parenthesized groups.
]


@pytest.mark.parametrize("src", VALID_SYNTAX_CASES)
def test_ast_round_trip_preserves_structure(src, capsys):
    """Ensures parsing -> stringifying -> parsing again yields the same AST."""
    # 1. First parse from the source string.
    ast1 = parse(src)
    # 2. Convert the resulting AST back to its string representation.
    re_stringified = str(ast1)
    # 3. Parse the stringified version to create a second AST.
    ast2 = parse(re_stringified)

    print(f"\nOriginal source : {src}")
    print(f"Stringified AST : {re_stringified}")
    print(f"Round-trip AST  : {ast2}")

    # The two ASTs must be structurally identical.
    assert ast1 == ast2, "AST structure changed after stringifying and re-parsing"
    _ = capsys.readouterr()


# A list of malformed inputs that should trigger a ParseError.
INVALID_SYNTAX_CASES = [
    # --- Parenthesis Errors ---
    "EP(p",             # Mismatched parenthesis, unclosed EP.
    "(p & q))",         # Unbalanced right parenthesis.
    "a | (b & c",      # Unclosed parenthesis in a nested expression.
    "a | b) & c",      # Unopened parenthesis.
    "()",               # Empty expression within parentheses.

    # --- Operator Errors ---
    "p | | q",          # Double operator.
    "p &",              # Trailing operator.
    "p q",              # Missing operator between literals.
    "p ! q",            # Infix NOT operator is invalid.
    "p & ( | q)",      # Operator adjacent to a parenthesis.
    "!&p",              # Nonsensical sequence of operators.
    "p | q &",          # Trailing operator after a valid expression.
    "!(p q)",           # Missing operator inside a negated group.

    # --- Keyword and Token Errors ---
    "EP p",             # EP keyword used without parentheses.
    "EP()",             # EP with an empty argument.
    "p AND q",          # Using invalid keyword "AND" instead of '&'.
    "EP(!)",            # An operator cannot be an operand.
    "p; q",             # Use of an illegal character as a separator.

    # --- Empty/Whitespace Errors ---
    "",                 # Empty input string.
    "     ",            # Whitespace only.
]


@pytest.mark.parametrize("src", INVALID_SYNTAX_CASES)
def test_parser_raises_on_invalid_syntax(src, capsys):
    """Ensures that malformed input strings raise a ParseError from the base parser."""
    print(f"\nTesting invalid input for parse(): '{src}'")
    with pytest.raises(ParseError) as exc_info:
        parse(src)
    # Verifies that the specific, expected exception is caught.
    print(f"Successfully caught expected error: {exc_info.value}")
    _ = capsys.readouterr()


@pytest.mark.parametrize("src", INVALID_SYNTAX_CASES)
def test_transformer_raises_on_invalid_syntax(src, capsys):
    """Ensures that malformed input strings raise a ParseError from the DLNF transformer entrypoint."""
    print(f"\nTesting invalid input for parse_and_dlnf(): '{src}'")
    # The ParseError should be raised by the parsing step before the transformer is even called.
    with pytest.raises(ParseError) as exc_info:
        parse_and_dlnf(src)
    print(f"Successfully caught expected error: {exc_info.value}")
    _ = capsys.readouterr()