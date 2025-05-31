# tests/parser_tests/test_precedence.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Test suite for PBTL parser operator precedence and associativity

"""Test suite for PBTL parser operator precedence and associativity.

This module verifies that the parser correctly interprets expressions according
to the specified operator precedence rules and associativity. Tests ensure
proper handling of precedence overrides via parentheses and correct grouping
of chained operators.

Operator precedence (highest to lowest):
1. () - parentheses for grouping
2. EP(...) - temporal operator
3. ! - negation (right-associative)
4. & - conjunction (left-associative)
5. | - disjunction (left-associative)
"""

import pytest
from parser import parse
from parser.ast_nodes import And, Or, Not, Literal, EP
from utils.logger import get_logger


class TestPBTLPrecedence:
    """Test cases for PBTL operator precedence and associativity."""

    def setup_method(self):
        """Initialize logger for each test method."""
        self.logger = get_logger()

    # Test cases: (input_formula, expected_ast_structure)
    PRECEDENCE_TEST_CASES = [
        # Basic precedence: AND vs OR (AND binds tighter)
        ("a | b & c", Or(Literal("a"), And(Literal("b"), Literal("c")))),
        ("a & b | c", Or(And(Literal("a"), Literal("b")), Literal("c"))),
        (
            "a | b & c | d",
            Or(Or(Literal("a"), And(Literal("b"), Literal("c"))), Literal("d")),
        ),
        # Unary NOT precedence (NOT binds tightest)
        ("!a & b", And(Not(Literal("a")), Literal("b"))),
        ("!a & b | c", Or(And(Not(Literal("a")), Literal("b")), Literal("c"))),
        ("a | !b & c", Or(Literal("a"), And(Not(Literal("b")), Literal("c")))),
        ("!a | b & !c", Or(Not(Literal("a")), And(Literal("b"), Not(Literal("c"))))),
        (
            "!a & !b | !c",
            Or(And(Not(Literal("a")), Not(Literal("b"))), Not(Literal("c"))),
        ),
        # Parentheses overriding precedence
        ("a & (b | c)", And(Literal("a"), Or(Literal("b"), Literal("c")))),
        ("(a | b) & c", And(Or(Literal("a"), Literal("b")), Literal("c"))),
        ("!(a | b) & c", And(Not(Or(Literal("a"), Literal("b"))), Literal("c"))),
        (
            "a & (b | (c & !d))",
            And(Literal("a"), Or(Literal("b"), And(Literal("c"), Not(Literal("d"))))),
        ),
        # Associativity: left-associative for AND/OR
        ("a & b & c", And(And(Literal("a"), Literal("b")), Literal("c"))),
        ("a | b | c", Or(Or(Literal("a"), Literal("b")), Literal("c"))),
        # NOT is right-associative
        ("!!!p", Not(Not(Not(Literal("p"))))),
        # Complex chains testing precedence and associativity
        (
            "a & b | c & d | e",
            Or(
                Or(And(Literal("a"), Literal("b")), And(Literal("c"), Literal("d"))),
                Literal("e"),
            ),
        ),
        # EP operator precedence
        ("!EP(p)", Not(EP(Literal("p")))),
        ("EP(p) & q", And(EP(Literal("p")), Literal("q"))),
        ("EP(p | q & r)", EP(Or(Literal("p"), And(Literal("q"), Literal("r"))))),
        ("EP((p | q) & r)", EP(And(Or(Literal("p"), Literal("q")), Literal("r")))),
        ("(EP(p) | q) & r", And(Or(EP(Literal("p")), Literal("q")), Literal("r"))),
        # Boolean constants in precedence
        (
            "true | false & true",
            Or(Literal("true"), And(Literal("false"), Literal("true"))),
        ),
        ("!true & false", And(Not(Literal("true")), Literal("false"))),
        (
            "EP(true & p | false)",
            EP(Or(And(Literal("true"), Literal("p")), Literal("false"))),
        ),
    ]

    @pytest.mark.parametrize("input_formula, expected_ast", PRECEDENCE_TEST_CASES)
    def test_operator_precedence_structure(self, input_formula, expected_ast):
        """Test that parser builds AST respecting operator precedence.

        Args:
            input_formula: PBTL formula string to parse
            expected_ast: Expected AST structure with correct precedence
        """
        self.logger.debug(f"Testing precedence for: {input_formula}")

        actual_ast = parse(input_formula)

        self.logger.debug(f"Input: {input_formula}")
        self.logger.debug(f"Expected: {expected_ast}")
        self.logger.debug(f"Actual: {actual_ast}")

        assert actual_ast == expected_ast, (
            f"Precedence structure mismatch for: {input_formula}\n"
            f"Expected: {expected_ast}\n"
            f"Actual: {actual_ast}"
        )

    def test_and_or_precedence(self):
        """Test that AND binds tighter than OR."""
        test_cases = [
            ("p | q & r", Or(Literal("p"), And(Literal("q"), Literal("r")))),
            ("p & q | r", Or(And(Literal("p"), Literal("q")), Literal("r"))),
            (
                "p | q & r | s",
                Or(Or(Literal("p"), And(Literal("q"), Literal("r"))), Literal("s")),
            ),
        ]

        for formula, expected in test_cases:
            self.logger.debug(f"Testing AND/OR precedence: {formula}")
            actual = parse(formula)
            assert actual == expected, f"AND/OR precedence failed for: {formula}"

    def test_not_precedence(self):
        """Test that NOT binds tighter than AND and OR."""
        test_cases = [
            ("!p & q", And(Not(Literal("p")), Literal("q"))),
            ("!p | q", Or(Not(Literal("p")), Literal("q"))),
            ("p & !q", And(Literal("p"), Not(Literal("q")))),
            ("!p & !q", And(Not(Literal("p")), Not(Literal("q")))),
        ]

        for formula, expected in test_cases:
            self.logger.debug(f"Testing NOT precedence: {formula}")
            actual = parse(formula)
            assert actual == expected, f"NOT precedence failed for: {formula}"

    def test_ep_precedence(self):
        """Test EP operator precedence in expressions."""
        test_cases = [
            ("EP(p) & q", And(EP(Literal("p")), Literal("q"))),
            ("EP(p) | q", Or(EP(Literal("p")), Literal("q"))),
            ("!EP(p)", Not(EP(Literal("p")))),
            ("EP(p & q) | r", Or(EP(And(Literal("p"), Literal("q"))), Literal("r"))),
        ]

        for formula, expected in test_cases:
            self.logger.debug(f"Testing EP precedence: {formula}")
            actual = parse(formula)
            assert actual == expected, f"EP precedence failed for: {formula}"

    def test_left_associativity(self):
        """Test that AND and OR are left-associative."""
        and_cases = [
            ("a & b & c", And(And(Literal("a"), Literal("b")), Literal("c"))),
            (
                "a & b & c & d",
                And(And(And(Literal("a"), Literal("b")), Literal("c")), Literal("d")),
            ),
        ]

        or_cases = [
            ("a | b | c", Or(Or(Literal("a"), Literal("b")), Literal("c"))),
            (
                "a | b | c | d",
                Or(Or(Or(Literal("a"), Literal("b")), Literal("c")), Literal("d")),
            ),
        ]

        for formula, expected in and_cases + or_cases:
            self.logger.debug(f"Testing left associativity: {formula}")
            actual = parse(formula)
            assert actual == expected, f"Left associativity failed for: {formula}"

    def test_right_associativity_not(self):
        """Test that NOT is right-associative."""
        test_cases = [
            ("!!p", Not(Not(Literal("p")))),
            ("!!!p", Not(Not(Not(Literal("p"))))),
            ("!!!!p", Not(Not(Not(Not(Literal("p")))))),
        ]

        for formula, expected in test_cases:
            self.logger.debug(f"Testing NOT right associativity: {formula}")
            actual = parse(formula)
            assert actual == expected, f"NOT right associativity failed for: {formula}"

    def test_parentheses_override_precedence(self):
        """Test that parentheses correctly override operator precedence."""
        test_cases = [
            ("(p | q) & r", And(Or(Literal("p"), Literal("q")), Literal("r"))),
            ("p & (q | r)", And(Literal("p"), Or(Literal("q"), Literal("r")))),
            ("!(p & q)", Not(And(Literal("p"), Literal("q")))),
            ("!(p | q) & r", And(Not(Or(Literal("p"), Literal("q"))), Literal("r"))),
        ]

        for formula, expected in test_cases:
            self.logger.debug(f"Testing parentheses override: {formula}")
            actual = parse(formula)
            assert actual == expected, f"Parentheses override failed for: {formula}"

    def test_complex_precedence_chains(self):
        """Test complex expressions with multiple precedence levels."""
        complex_cases = [
            # Mix of all operators with precedence
            ("!p & q | r", Or(And(Not(Literal("p")), Literal("q")), Literal("r"))),
            ("p | !q & r", Or(Literal("p"), And(Not(Literal("q")), Literal("r")))),
            (
                "EP(p) & !q | r",
                Or(And(EP(Literal("p")), Not(Literal("q"))), Literal("r")),
            ),
            # Nested EP with complex expressions
            (
                "EP(!p & q | r)",
                EP(Or(And(Not(Literal("p")), Literal("q")), Literal("r"))),
            ),
            (
                "!EP(p & q) | r",
                Or(Not(EP(And(Literal("p"), Literal("q")))), Literal("r")),
            ),
        ]

        for formula, expected in complex_cases:
            self.logger.debug(f"Testing complex precedence: {formula}")
            actual = parse(formula)
            assert actual == expected, f"Complex precedence failed for: {formula}"

    def test_precedence_with_boolean_constants(self):
        """Test precedence handling with boolean constants."""
        test_cases = [
            (
                "true & false | true",
                Or(And(Literal("true"), Literal("false")), Literal("true")),
            ),
            ("!false & true", And(Not(Literal("false")), Literal("true"))),
            ("EP(true) | false", Or(EP(Literal("true")), Literal("false"))),
        ]

        for formula, expected in test_cases:
            self.logger.debug(f"Testing precedence with constants: {formula}")
            actual = parse(formula)
            assert (
                actual == expected
            ), f"Precedence with constants failed for: {formula}"

    def test_deeply_nested_precedence(self):
        """Test precedence in deeply nested expressions."""
        nested_cases = [
            (
                "a & (b | (c & d))",
                And(Literal("a"), Or(Literal("b"), And(Literal("c"), Literal("d")))),
            ),
            (
                "(a | b) & (c | d)",
                And(Or(Literal("a"), Literal("b")), Or(Literal("c"), Literal("d"))),
            ),
            (
                "EP(a & (b | c)) | d",
                Or(EP(And(Literal("a"), Or(Literal("b"), Literal("c")))), Literal("d")),
            ),
        ]

        for formula, expected in nested_cases:
            self.logger.debug(f"Testing deeply nested precedence: {formula}")
            actual = parse(formula)
            assert actual == expected, f"Deeply nested precedence failed for: {formula}"
