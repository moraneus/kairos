# tests/parser_test/test_lexer_tokens.py


"""
Tests the behavior of the PBTL lexer.

This test suite verifies two key functions of the lexer:

1.  **Correct Tokenization**: Ensures that valid sequences of characters are
    correctly tagged with their specific token types (e.g., 'EP' is a keyword,
    'p' is an identifier, '!' is an operator). It pays special attention to
    distinguishing keywords from identifiers.

2.  **Error Handling**: Ensures that any character not part of the defined
    PBTL language syntax causes the lexer to raise a `ValueError`.
"""
import pytest
from parser.lexer import PBTLLexer

# Instantiate the lexer once for all tests in this module.
lexer = PBTLLexer()


def _get_token_types(text: str):
    """A helper function to tokenize a string and return only the token types."""
    return [tok.type for tok in lexer.tokenize(text)]


# A comprehensive list of tokenization test cases.
TOKENIZATION_SCENARIOS = [
    # --- Basic Keyword and Identifier Tests ---
    # A standard expression with an identifier.
    ("EP(foo)", ["EP", "LPAREN", "ID", "RPAREN"]),
    # The 'true' keyword must be identified as TRUE, not a generic ID.
    ("true", ["TRUE"]),
    # The 'false' keyword must be identified as FALSE.
    ("false", ["FALSE"]),
    # A standard identifier should be recognized as ID.
    ("a_valid_identifier", ["ID"]),

    # --- Keyword vs. Identifier Ambiguity Tests ---
    # The lexer must be case-sensitive; 'ep' is an ID, not the EP keyword.
    ("ep", ["ID"]),
    # Case-sensitivity also applies to boolean constants.
    ("True", ["ID"]),
    # When a keyword is a prefix of an identifier, it should be one ID token.
    ("EPtrue", ["ID"]),
    # A keyword as a suffix should also be treated as part of the identifier.
    ("falseEP", ["ID"]),
    # An identifier can contain a keyword substring.
    ("id_containing_true_keyword", ["ID"]),
    # Underscores adjacent to keywords are part of the identifier.
    ("EP_is_an_id", ["ID"]),

    # --- Operator and Punctuation Tests ---
    # All single-character operators and parentheses.
    ("! & | ( )", ["NOT", "AND", "OR", "LPAREN", "RPAREN"]),
    # An expression without whitespace to test token boundaries.
    ("p&q|!r", ["ID", "AND", "ID", "OR", "NOT", "ID"]),
    # Parentheses are distinct tokens.
    ("()", ["LPAREN", "RPAREN"]),

    # --- Whitespace and Combination Tests ---
    # The lexer should correctly ignore various forms of whitespace.
    (" \t EP \n (p) ", ["EP", "LPAREN", "ID", "RPAREN"]),
    # A complex expression combining keywords, identifiers, and operators.
    ("EP( an_id | true ) & !false", [
        "EP", "LPAREN", "ID", "OR", "TRUE", "RPAREN",
        "AND", "NOT", "FALSE"
    ]),
]


@pytest.mark.parametrize("snippet, expected_types", TOKENIZATION_SCENARIOS)
def test_tokenization_scenarios(snippet, expected_types, capsys):
    """
    Verifies that the lexer correctly tokenizes various valid syntax snippets.
    """
    actual_types = _get_token_types(snippet)

    print(f"\nInput snippet: '{snippet}'")
    print(f"Expected types: {expected_types}")
    print(f"Actual types  : {actual_types}")

    assert actual_types == expected_types
    _ = capsys.readouterr()


# A list of single illegal characters that should cause the lexer to fail.
ILLEGAL_CHARACTERS = [
    "@", "#", "$", "%", "^", "*", "=", "`", "~", "?",
    ":", ";", ".", ",", "<", ">", "/", "[", "]", "{", "}",
]


@pytest.mark.parametrize("illegal_char", ILLEGAL_CHARACTERS)
def test_lexer_raises_on_illegal_character(illegal_char, capsys):
    """
    Verifies that the lexer raises a ValueError for any character
    that is not part of the defined language syntax.
    """
    # Embed the illegal character in a valid formula to test its detection.
    formula_with_illegal_char = f"p & {illegal_char}"

    print(f"\nTesting illegal snippet: '{formula_with_illegal_char}'")

    with pytest.raises(ValueError) as exc_info:
        _get_token_types(formula_with_illegal_char)

    # The lexer's error method is designed to raise a ValueError.
    print(f"Successfully caught expected error: {exc_info.value}")
    assert "Illegal character" in str(exc_info.value)
    _ = capsys.readouterr()