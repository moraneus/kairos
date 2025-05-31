# tests/parser_tests/test_parse_basic.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Test suite for basic PBTL parser functionality and round-trip integrity

"""Test suite for basic PBTL parser functionality and AST integrity.

This module tests the parser's ability to correctly parse valid PBTL formulas
and maintain structural integrity through parse -> stringify -> parse cycles.
Ensures AST string representations are syntactically correct and unambiguous.
"""

import pytest
from parser import parse
from utils.logger import get_logger


class TestPBTLParserBasic:
    """Test cases for basic PBTL parser functionality and round-trip integrity."""

    def setup_method(self):
        """Initialize logger for each test method."""
        self.logger = get_logger()

    # Comprehensive set of valid PBTL formulas for testing
    VALID_FORMULAS = [
        # Basic literals and operators
        "p",
        "!q",
        "p & q",
        "p | r",
        "EP(s)",
        # Precedence and associativity
        "p & q | r",  # AND has higher precedence than OR
        "p | q & r",  # Confirms AND is evaluated before OR
        "a & b & c",  # Ensures AND is left-associative
        "a | b | c",  # Ensures OR is left-associative
        "!!!p",  # Multiple unary NOT operators
        # Parentheses and grouping
        "p & (q | r)",  # Parentheses override default precedence
        "!(p & q)",  # Negation of grouped expression
        "((p))",  # Redundant parentheses
        "(p & q) | (r & s)",  # Multiple grouped expressions
        # Temporal operator (EP) combinations
        "EP(p & q)",  # Conjunction inside EP
        "!EP(p)",  # Negation of temporal expression
        "EP(p) & q",  # Temporal expression in conjunction
        "EP(EP(p))",  # Nested temporal operators
        "EP(p | !q)",  # Negation within temporal operand
        "EP(p) | EP(q)",  # Disjunction of temporal expressions
        # Complex nested expressions
        "!((p | q) & (r | s))",  # Complex negated expression
        "EP(p & (q | (r & !s)))",  # Deep nesting inside EP
        "a & (b | (c & (d | (e & f))))",  # Very deep right-associative nesting
        # Boolean constants
        "true",
        "false",
        "!false",
        "(p | true) & !false",
        # Whitespace handling
        " p\n& \tq ",  # Various whitespace characters
        "  EP(p)  ",  # Leading/trailing whitespace
        # Complex identifier patterns
        "variable_123",
        "_underscore_start",
        "id_with_EP_substring",
        # Mixed complexity cases
        "EP(true | false) & !EP(p & q)",
        "((EP(p) | !q) & (r | EP(s)))",
        "!(EP(a | b) & (c | !EP(d)))",
    ]

    @pytest.mark.parametrize("formula", VALID_FORMULAS)
    def test_round_trip_ast_integrity(self, formula):
        """Test that parse -> stringify -> parse preserves AST structure.

        Verifies that for any valid formula:
        1. Parse source string into AST
        2. Convert AST back to string representation
        3. Parse the string representation into new AST
        4. Both ASTs are structurally identical

        Args:
            formula: Valid PBTL formula string
        """
        self.logger.debug(f"Testing round-trip integrity for: {formula}")

        # Parse original formula
        original_ast = parse(formula)

        # Convert AST to canonical string representation
        stringified = str(original_ast)

        # Parse the stringified version
        reparsed_ast = parse(stringified)

        self.logger.debug(f"Original: {formula!r}")
        self.logger.debug(f"Stringified: {stringified!r}")
        self.logger.debug(f"Structures equal: {original_ast == reparsed_ast}")

        assert original_ast == reparsed_ast, (
            f"AST structure changed during round-trip:\n"
            f"Original: {formula!r}\n"
            f"Stringified: {stringified!r}\n"
            f"Original AST: {original_ast}\n"
            f"Reparsed AST: {reparsed_ast}"
        )

    def test_basic_literal_parsing(self):
        """Test parsing of basic literals and constants."""
        basic_cases = [
            ("p", "Literal"),
            ("true", "Literal"),
            ("false", "Literal"),
            ("variable_123", "Literal"),
            ("_underscore", "Literal"),
        ]

        for formula, expected_type in basic_cases:
            self.logger.debug(f"Testing basic literal: {formula}")

            ast = parse(formula)
            assert ast is not None
            assert type(ast).__name__ == expected_type

            # Verify round-trip
            stringified = str(ast)
            reparsed = parse(stringified)
            assert ast == reparsed

    def test_operator_parsing(self):
        """Test parsing of all PBTL operators."""
        operator_cases = [
            ("!p", "Not"),
            ("p & q", "And"),
            ("p | q", "Or"),
            ("EP(p)", "EP"),
        ]

        for formula, expected_type in operator_cases:
            self.logger.debug(f"Testing operator: {formula}")

            ast = parse(formula)
            assert ast is not None
            assert type(ast).__name__ == expected_type

            # Verify round-trip
            stringified = str(ast)
            reparsed = parse(stringified)
            assert ast == reparsed

    def test_precedence_preservation(self):
        """Test that operator precedence is correctly preserved in round-trips."""
        precedence_cases = [
            "!p & q",  # NOT binds tighter than AND
            "p & q | r",  # AND binds tighter than OR
            "!p | q & r",  # Complex precedence chain
            "EP(p) & q | r",  # EP in precedence chain
        ]

        for formula in precedence_cases:
            self.logger.debug(f"Testing precedence preservation: {formula}")

            original_ast = parse(formula)
            stringified = str(original_ast)
            reparsed_ast = parse(stringified)

            assert original_ast == reparsed_ast, (
                f"Precedence not preserved for: {formula}\n"
                f"Stringified: {stringified}"
            )

    def test_associativity_preservation(self):
        """Test that operator associativity is correctly preserved."""
        associativity_cases = [
            "a & b & c",  # AND is left-associative
            "a | b | c",  # OR is left-associative
            "!(!(!p))",  # NOT is right-associative
        ]

        for formula in associativity_cases:
            self.logger.debug(f"Testing associativity preservation: {formula}")

            original_ast = parse(formula)
            stringified = str(original_ast)
            reparsed_ast = parse(stringified)

            assert original_ast == reparsed_ast, (
                f"Associativity not preserved for: {formula}\n"
                f"Stringified: {stringified}"
            )

    def test_nested_expression_parsing(self):
        """Test parsing of deeply nested expressions."""
        nested_cases = [
            "((p))",
            "(((p & q)))",
            "EP(EP(EP(p)))",
            "!(!(!(p)))",
            "EP(p & (q | (r & s)))",
        ]

        for formula in nested_cases:
            self.logger.debug(f"Testing nested expression: {formula}")

            original_ast = parse(formula)
            stringified = str(original_ast)
            reparsed_ast = parse(stringified)

            assert original_ast == reparsed_ast, (
                f"Nested structure not preserved for: {formula}\n"
                f"Stringified: {stringified}"
            )

    def test_whitespace_normalization(self):
        """Test that whitespace is properly handled and normalized."""
        whitespace_cases = [
            ("  p  ", "p"),
            (" p & q ", "(p & q)"),
            ("\tEP(p)\n", "EP(p)"),
            ("p\t&\nq", "(p & q)"),
        ]

        for input_formula, expected_base in whitespace_cases:
            self.logger.debug(f"Testing whitespace handling: {input_formula!r}")

            ast = parse(input_formula)
            stringified = str(ast)

            # Parse expected base to compare structure
            expected_ast = parse(expected_base)

            assert ast == expected_ast, (
                f"Whitespace handling failed for: {input_formula!r}\n"
                f"Got: {stringified}\n"
                f"Expected structure like: {expected_base}"
            )

    def test_string_representation_validity(self):
        """Test that AST string representations are valid PBTL syntax."""
        complex_formulas = [
            "EP(p & q) | !EP(r | s)",
            "((a & b) | (c & d)) & !(e | f)",
            "EP(EP(p | q) & (r | !s))",
        ]

        for formula in complex_formulas:
            self.logger.debug(f"Testing string representation validity: {formula}")

            # Parse and stringify multiple times
            ast1 = parse(formula)
            str1 = str(ast1)

            ast2 = parse(str1)
            str2 = str(ast2)

            ast3 = parse(str2)

            # All should be equivalent
            assert ast1 == ast2 == ast3, (
                f"String representation not stable for: {formula}\n"
                f"First stringify: {str1}\n"
                f"Second stringify: {str2}"
            )
