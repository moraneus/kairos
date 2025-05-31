# tests/parser_tests/test_lexer_tokens.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Test suite for PBTL lexer tokenization and error handling

"""Test suite for PBTL lexer functionality.

This module tests the lexical analysis phase of PBTL formula parsing,
verifying correct tokenization of valid syntax and proper error handling
for invalid characters.
"""

import pytest
from parser.lexer import PBTLLexer
from utils.logger import get_logger


class TestPBTLLexer:
    """Test cases for PBTL lexer tokenization and error handling."""

    def setup_method(self):
        """Initialize lexer for each test method."""
        self.lexer = PBTLLexer()
        self.logger = get_logger()

    def _tokenize_to_types(self, text: str) -> list[str]:
        """Extract token types from input text.

        Args:
            text: Input string to tokenize

        Returns:
            List of token type strings
        """
        self.logger.debug(f"Tokenizing: '{text}'")
        token_types = [token.type for token in self.lexer.tokenize(text)]
        self.logger.debug(f"Token types: {token_types}")
        return token_types

    # Test cases for valid tokenization scenarios
    VALID_TOKENIZATION_CASES = [
        # Basic keyword and identifier recognition
        ("EP(foo)", ["EP", "LPAREN", "ID", "RPAREN"]),
        ("true", ["TRUE"]),
        ("false", ["FALSE"]),
        ("a_valid_identifier", ["ID"]),
        # Case sensitivity verification
        ("ep", ["ID"]),
        ("True", ["ID"]),
        ("False", ["ID"]),
        # Keyword-identifier boundary cases
        ("EPtrue", ["ID"]),
        ("falseEP", ["ID"]),
        ("id_containing_true_keyword", ["ID"]),
        ("EP_is_an_id", ["ID"]),
        # Operator and punctuation tokenization
        ("! & | ( )", ["NOT", "AND", "OR", "LPAREN", "RPAREN"]),
        ("p&q|!r", ["ID", "AND", "ID", "OR", "NOT", "ID"]),
        ("()", ["LPAREN", "RPAREN"]),
        # Whitespace handling
        (" \t EP \n (p) ", ["EP", "LPAREN", "ID", "RPAREN"]),
        # Complex expressions
        (
            "EP( an_id | true ) & !false",
            ["EP", "LPAREN", "ID", "OR", "TRUE", "RPAREN", "AND", "NOT", "FALSE"],
        ),
    ]

    @pytest.mark.parametrize("input_text, expected_types", VALID_TOKENIZATION_CASES)
    def test_valid_tokenization(self, input_text, expected_types):
        """Test lexer correctly tokenizes valid PBTL syntax.

        Args:
            input_text: Valid PBTL syntax string
            expected_types: Expected sequence of token types
        """
        actual_types = self._tokenize_to_types(input_text)

        assert actual_types == expected_types, (
            f"Tokenization mismatch for '{input_text}':\n"
            f"Expected: {expected_types}\n"
            f"Actual: {actual_types}"
        )

    def test_keyword_recognition(self):
        """Test proper recognition of PBTL keywords vs identifiers."""
        keyword_cases = [
            ("EP", ["EP"]),
            ("true", ["TRUE"]),
            ("false", ["FALSE"]),
        ]

        for keyword, expected in keyword_cases:
            actual = self._tokenize_to_types(keyword)
            assert actual == expected, f"Keyword '{keyword}' not recognized correctly"

    def test_identifier_recognition(self):
        """Test proper recognition of various identifier patterns."""
        identifier_cases = [
            "simple_id",
            "id123",
            "_underscore_start",
            "camelCaseId",
            "id_with_numbers_123",
            "very_long_identifier_name_with_underscores",
        ]

        for identifier in identifier_cases:
            actual = self._tokenize_to_types(identifier)
            assert actual == ["ID"], f"Identifier '{identifier}' not recognized as ID"

    def test_operator_tokenization(self):
        """Test tokenization of all PBTL operators."""
        operator_cases = [
            ("!", ["NOT"]),
            ("&", ["AND"]),
            ("|", ["OR"]),
            ("(", ["LPAREN"]),
            (")", ["RPAREN"]),
        ]

        for operator, expected in operator_cases:
            actual = self._tokenize_to_types(operator)
            assert actual == expected, f"Operator '{operator}' not tokenized correctly"

    # Invalid characters that should trigger lexer errors
    ILLEGAL_CHARACTERS = [
        "@",
        "#",
        "$",
        "%",
        "^",
        "*",
        "=",
        "`",
        "~",
        "?",
        ":",
        ";",
        ".",
        ",",
        "<",
        ">",
        "/",
        "[",
        "]",
        "{",
        "}",
        '"',
        "'",
        "\\",
        "+",
        "-",
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
    ]

    @pytest.mark.parametrize("illegal_char", ILLEGAL_CHARACTERS)
    def test_illegal_character_handling(self, illegal_char):
        """Test lexer raises ValueError for illegal characters.

        Args:
            illegal_char: Character not allowed in PBTL syntax
        """
        # Embed illegal character in otherwise valid formula
        test_input = f"p & {illegal_char}"

        self.logger.debug(f"Testing illegal character: '{illegal_char}'")

        with pytest.raises(ValueError) as exc_info:
            self._tokenize_to_types(test_input)

        error_message = str(exc_info.value)
        assert (
            "Illegal character" in error_message
        ), f"Expected 'Illegal character' in error message, got: {error_message}"
        assert (
            illegal_char in error_message
        ), f"Expected illegal character '{illegal_char}' in error message"

    def test_whitespace_handling(self):
        """Test lexer properly ignores various whitespace characters."""
        whitespace_cases = [
            ("  EP(p)  ", ["EP", "LPAREN", "ID", "RPAREN"]),
            ("\tEP\n(\rp\t)\n", ["EP", "LPAREN", "ID", "RPAREN"]),
            ("EP ( p )", ["EP", "LPAREN", "ID", "RPAREN"]),
        ]

        for input_text, expected in whitespace_cases:
            actual = self._tokenize_to_types(input_text)
            assert actual == expected, f"Whitespace handling failed for: '{input_text}'"

    def test_empty_input(self):
        """Test lexer behavior with empty input."""
        actual = self._tokenize_to_types("")
        assert actual == [], "Empty input should produce no tokens"

    def test_adjacent_tokens(self):
        """Test tokenization of adjacent tokens without whitespace."""
        adjacent_cases = [
            ("EP(p)", ["EP", "LPAREN", "ID", "RPAREN"]),
            ("!true", ["NOT", "TRUE"]),
            ("p&q|r", ["ID", "AND", "ID", "OR", "ID"]),
            ("(p|q)", ["LPAREN", "ID", "OR", "ID", "RPAREN"]),
        ]

        for input_text, expected in adjacent_cases:
            actual = self._tokenize_to_types(input_text)
            assert (
                actual == expected
            ), f"Adjacent tokenization failed for: '{input_text}'"
