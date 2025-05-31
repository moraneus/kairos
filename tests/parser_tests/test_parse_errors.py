# tests/parser_tests/test_parse_errors.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Test suite for PBTL parser syntax validation and error handling

"""Test suite for PBTL parser syntax validation and error handling.

This module tests the parser's ability to correctly handle valid syntax
and properly reject invalid input with appropriate error messages.
Tests cover round-trip parsing integrity and comprehensive error detection.
"""

import pytest
from parser import parse, parse_and_dlnf, ParseError
from utils.logger import get_logger


class TestPBTLParserSyntax:
    """Test cases for PBTL parser syntax validation and error handling."""

    def setup_method(self):
        """Initialize logger for each test method."""
        self.logger = get_logger()

    # Valid PBTL formulas for round-trip testing
    VALID_FORMULAS = [
        # Basic expressions
        "p",
        "!q",
        "(p & q)",
        "EP(r)",
        "(EP(p) | EP(!q))",
        # Complex nesting and precedence
        "EP((p & q) | !r)",
        "!(p | EP(q))",
        "EP(EP(EP(p)))",
        "(!p | !q)",
        "(p & (q | (r & (s | t))))",
        # Boolean constants
        "EP(true)",
        "EP(false)",
        "(true & false)",
        # Whitespace handling
        "  (p | q)  ",
        "\t EP(p) \n",
        # Complex identifiers
        "EP(id_with_EP_in_it)",
        "variable_123",
        "_underscore_var",
        # Multiple parenthesized groups
        "(a | b) & (c | !d)",
        "EP(p | q) & EP(r | s)",
    ]

    @pytest.mark.parametrize("formula", VALID_FORMULAS)
    def test_round_trip_parsing_integrity(self, formula):
        """Test that parsing -> stringifying -> parsing preserves AST structure.

        Args:
            formula: Valid PBTL formula string
        """
        self.logger.debug(f"Testing round-trip for: {formula}")

        # Parse original formula
        original_ast = parse(formula)

        # Convert AST back to string representation
        stringified = str(original_ast)

        # Parse the stringified version
        reparsed_ast = parse(stringified)

        self.logger.debug(f"Original: {formula}")
        self.logger.debug(f"Stringified: {stringified}")
        self.logger.debug(f"Reparsed equals original: {original_ast == reparsed_ast}")

        assert original_ast == reparsed_ast, (
            f"Round-trip parsing failed:\n"
            f"Original: {formula}\n"
            f"Stringified: {stringified}\n"
            f"ASTs are not equal"
        )

    @pytest.mark.parametrize("formula", VALID_FORMULAS)
    def test_dlnf_round_trip_parsing(self, formula):
        """Test round-trip parsing with DLNF transformation.

        Args:
            formula: Valid PBTL formula string
        """
        self.logger.debug(f"Testing DLNF round-trip for: {formula}")

        # Transform to DLNF
        dlnf_ast = parse_and_dlnf(formula)
        dlnf_string = str(dlnf_ast)

        # Parse the DLNF string
        reparsed_ast = parse(dlnf_string)

        assert dlnf_ast == reparsed_ast, (
            f"DLNF round-trip failed:\n"
            f"Original: {formula}\n"
            f"DLNF: {dlnf_string}\n"
            f"ASTs are not equal"
        )

    # Invalid syntax cases that should raise ParseError
    INVALID_SYNTAX_CASES = [
        # Parenthesis errors
        ("EP(p", "Mismatched parenthesis - unclosed EP"),
        ("(p & q))", "Unbalanced right parenthesis"),
        ("a | (b & c", "Unclosed parenthesis in nested expression"),
        ("a | b) & c", "Unopened parenthesis"),
        ("()", "Empty expression within parentheses"),
        # Operator errors
        ("p | | q", "Double operator"),
        ("p &", "Trailing operator"),
        ("p q", "Missing operator between literals"),
        ("p ! q", "Infix NOT operator invalid"),
        ("p & ( | q)", "Operator adjacent to parenthesis"),
        ("!&p", "Invalid operator sequence"),
        ("p | q &", "Trailing operator after expression"),
        ("!(p q)", "Missing operator inside negated group"),
        # EP syntax errors
        ("EP p", "EP keyword without parentheses"),
        ("EP()", "EP with empty argument"),
        ("EP(!)", "Operator cannot be EP operand"),
        # Invalid keywords/tokens
        ("p AND q", "Invalid keyword AND instead of &"),
        ("p OR q", "Invalid keyword OR instead of |"),
        ("NOT p", "Invalid keyword NOT instead of !"),
        ("p; q", "Illegal character as separator"),
        ("p @ q", "Illegal character in expression"),
        # Empty/whitespace errors
        ("", "Empty input string"),
        ("     ", "Whitespace only input"),
        ("\t\n", "Whitespace only with tabs/newlines"),
    ]

    @pytest.mark.parametrize("invalid_input, description", INVALID_SYNTAX_CASES)
    def test_parse_error_handling(self, invalid_input, description):
        """Test that invalid syntax raises ParseError from base parser.

        Args:
            invalid_input: Invalid PBTL syntax string
            description: Description of the syntax error
        """
        self.logger.debug(f"Testing parse error for: '{invalid_input}' ({description})")

        with pytest.raises(ParseError) as exc_info:
            parse(invalid_input)

        error_message = str(exc_info.value)
        self.logger.debug(f"Parse error message: {error_message}")

        # Verify we got a ParseError with some meaningful message
        assert len(error_message) > 0, "ParseError should have non-empty message"

    @pytest.mark.parametrize("invalid_input, description", INVALID_SYNTAX_CASES)
    def test_dlnf_parse_error_handling(self, invalid_input, description):
        """Test that invalid syntax raises ParseError from DLNF transformer.

        Args:
            invalid_input: Invalid PBTL syntax string
            description: Description of the syntax error
        """
        self.logger.debug(
            f"Testing DLNF parse error for: '{invalid_input}' ({description})"
        )

        with pytest.raises(ParseError) as exc_info:
            parse_and_dlnf(invalid_input)

        error_message = str(exc_info.value)
        self.logger.debug(f"DLNF parse error message: {error_message}")

        # Verify we got a ParseError with some meaningful message
        assert len(error_message) > 0, "ParseError should have non-empty message"

    def test_specific_error_messages(self):
        """Test that specific syntax errors produce informative messages."""
        error_cases = [
            ("EP(", "Unexpected end"),
            ("p &", "Unexpected end"),
            ("p | | q", "syntax error"),
        ]

        for invalid_input, expected_content in error_cases:
            self.logger.debug(f"Testing specific error message for: '{invalid_input}'")

            with pytest.raises(ParseError) as exc_info:
                parse(invalid_input)

            error_message = str(exc_info.value).lower()

            # Check that error message contains expected content
            assert any(
                content.lower() in error_message
                for content in [expected_content, "error", "syntax"]
            ), f"Error message should contain meaningful information: {error_message}"

    def test_nested_parentheses_validation(self):
        """Test validation of complex nested parentheses structures."""
        valid_nested = [
            "((p))",
            "(((p & q)))",
            "EP((p | (q & r)))",
            "((p | q) & (r | s))",
        ]

        invalid_nested = [
            "((p)",
            "(p))",
            "EP(((p))",
            "((p | q) & (r | s)",
        ]

        # Valid cases should parse successfully
        for formula in valid_nested:
            self.logger.debug(f"Testing valid nested: {formula}")
            ast = parse(formula)
            assert ast is not None

        # Invalid cases should raise ParseError
        for formula in invalid_nested:
            self.logger.debug(f"Testing invalid nested: {formula}")
            with pytest.raises(ParseError):
                parse(formula)

    def test_operator_precedence_validation(self):
        """Test that operator precedence is handled correctly in parsing."""
        precedence_cases = [
            ("!p & q", "(!p & q)"),  # NOT binds tighter than AND
            ("p & q | r", "((p & q) | r)"),  # AND binds tighter than OR
            ("!p | q & r", "(!p | (q & r))"),  # NOT first, then AND, then OR
        ]

        for input_formula, expected_structure in precedence_cases:
            self.logger.debug(f"Testing precedence for: {input_formula}")

            parsed_ast = parse(input_formula)
            expected_ast = parse(expected_structure)

            # The parsed formula should have the same structure as explicitly parenthesized version
            assert str(parsed_ast) == str(
                expected_ast
            ), f"Precedence handling incorrect for: {input_formula}"
