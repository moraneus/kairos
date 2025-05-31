# tests/parser_tests/test_dlnf_transformer.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# DLNF transformation test suite for PBTL formula conversion

"""Test suite for DLNF (Disjunctive Literal Normal Form) transformer.

This module contains comprehensive tests for the DLNF transformation algorithm
that converts PBTL formulas into canonical form suitable for efficient monitoring.
Tests verify correctness, structural properties, and idempotence of transformations.
"""

import re
import pytest
from parser import parse, parse_and_dlnf
from utils.logger import get_logger

# Pattern to detect OR operators within EP expressions (invalid in DLNF)
OR_IN_EP_PATTERN = re.compile(r"EP\([^()]*\|")


class TestDLNFTransformation:
    """Test cases for DLNF transformation correctness and properties."""

    # Test cases: (input_formula, expected_dlnf_output)
    TEST_CASES = [
        # Basic distribution cases
        ("EP(p | q)", "(EP(p) | EP(q))"),
        ("EP(p & q)", "EP((p & q))"),

        # Left-associative OR chains
        ("EP((p | q) | r)", "((EP(p) | EP(q)) | EP(r))"),
        ("EP((p & q) | r)", "(EP((p & q)) | EP(r))"),
        ("EP(p | q) | EP(r)", "((EP(p) | EP(q)) | EP(r))"),
        ("EP(a | b | c | d)", "(((EP(a) | EP(b)) | EP(c)) | EP(d))"),

        # DNF conversion within EP
        (
            "EP((p | q) & (r | s))",
            "(((EP((p & r)) | EP((p & s))) | EP((q & r))) | EP((q & s)))",
        ),
        (
            "EP(a|b) & EP(c|d)",
            "(((EP(a) & EP(c)) | (EP(a) & EP(d))) | (EP(b) & EP(c))) | (EP(b) & EP(d))",
        ),

        # Complex nested structures
        (
            "EP(a & (b | (c & (d | e))))",
            "((EP((a & b)) | EP(((a & c) & d))) | EP(((a & c) & e)))",
        ),

        # Negation and De Morgan's laws
        ("EP(!(p & q))", "(EP(!p) | EP(!q))"),
        ("EP(!!(p | q))", "(EP(p) | EP(q))"),
        ("EP(!(EP(p & q)))", "EP(!(EP((p & q))))"),
        ("EP(p | !(q & r))", "((EP(p) | EP(!q)) | EP(!r))"),
        ("EP(!((p | !q) & r))", "(EP((!p & q)) | EP(!r))"),

        # Nested EP expressions
        ("EP(p | EP(q | r))", "((EP(p) | EP(EP(q))) | EP(EP(r)))"),
        (
            "EP(a | (b & EP(c | (d & EP(e | f)))))",
            "(((EP(a) | EP((b & EP(c)))) | EP((b & EP((d & EP(e)))))) | EP((b & EP((d & EP(f))))))",
        ),
        (
            "EP(!(p & (q | EP(r | s))))",
            "(EP(!p) | EP(((!q & !EP(r)) & !EP(s))))"
        ),
    ]

    @pytest.mark.parametrize("input_formula, expected_output", TEST_CASES)
    def test_dlnf_transformation_correctness(self, input_formula, expected_output):
        """Test DLNF transformation produces correct output structure.

        Args:
            input_formula: Original PBTL formula string
            expected_output: Expected DLNF transformation result
        """
        logger = get_logger()
        logger.debug(f"Testing DLNF transformation: {input_formula}")

        # Transform input formula to DLNF
        transformed_ast = parse_and_dlnf(input_formula)
        transformed_str = str(transformed_ast)

        # Parse expected output for structural comparison
        expected_ast = parse(expected_output)

        logger.debug(f"Input: {input_formula}")
        logger.debug(f"Output: {transformed_str}")
        logger.debug(f"Expected: {expected_output}")

        # Verify structural correctness
        assert transformed_ast == expected_ast, (
            f"Transformation mismatch:\n"
            f"Input: {input_formula}\n"
            f"Got: {transformed_str}\n"
            f"Expected: {expected_output}"
        )

    @pytest.mark.parametrize("input_formula, expected_output", TEST_CASES)
    def test_dlnf_structure_validity(self, input_formula, expected_output):
        """Test that transformed formulas satisfy DLNF structural requirements.

        Args:
            input_formula: Original PBTL formula string
            expected_output: Expected DLNF transformation result
        """
        logger = get_logger()

        transformed_ast = parse_and_dlnf(input_formula)
        transformed_str = str(transformed_ast)

        logger.debug(f"Validating DLNF structure for: {transformed_str}")

        # Verify no OR operators exist within EP expressions
        assert not OR_IN_EP_PATTERN.search(transformed_str), (
            f"Invalid DLNF structure: Found '|' inside EP() in: {transformed_str}"
        )

    @pytest.mark.parametrize("input_formula, expected_output", TEST_CASES)
    def test_dlnf_transformation_idempotence(self, input_formula, expected_output):
        """Test that DLNF transformation is idempotent.

        Applying the transformation twice should yield identical results.

        Args:
            input_formula: Original PBTL formula string
            expected_output: Expected DLNF transformation result
        """
        logger = get_logger()

        # First transformation
        first_transform = parse_and_dlnf(input_formula)
        first_str = str(first_transform)

        # Second transformation (should be identical)
        second_transform = parse_and_dlnf(first_str)

        logger.debug(f"Testing idempotence for: {input_formula}")
        logger.debug(f"First transform: {first_str}")
        logger.debug(f"Second transform: {str(second_transform)}")

        assert first_transform == second_transform, (
            f"Transformation not idempotent:\n"
            f"Original: {input_formula}\n"
            f"First: {first_str}\n"
            f"Second: {str(second_transform)}"
        )

    def test_empty_formula_handling(self):
        """Test transformation behavior with edge cases."""
        logger = get_logger()

        # Test basic atomic formulas
        simple_cases = [
            ("p", "p"),
            ("!p", "!p"),
            ("true", "true"),
            ("false", "false"),
        ]

        for input_formula, expected in simple_cases:
            logger.debug(f"Testing simple case: {input_formula}")

            result = parse_and_dlnf(input_formula)
            result_str = str(result)

            assert result_str == expected, (
                f"Simple case failed: {input_formula} -> {result_str}, expected {expected}"
            )

    def test_complex_nested_formula(self):
        """Test transformation on highly complex nested formula."""
        logger = get_logger()

        complex_formula = "EP(EP(a | b) & (EP(c | d) | EP(e & f)))"
        logger.debug(f"Testing complex formula: {complex_formula}")

        result = parse_and_dlnf(complex_formula)
        result_str = str(result)

        # Verify no OR within EP
        assert not OR_IN_EP_PATTERN.search(result_str), (
            f"Complex formula contains invalid structure: {result_str}"
        )

        # Verify idempotence
        second_result = parse_and_dlnf(result_str)
        assert result == second_result, "Complex formula transformation not idempotent"

        logger.debug(f"Complex formula result: {result_str}")