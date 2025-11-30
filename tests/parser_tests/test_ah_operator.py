# tests/parser_tests/test_ah_operator.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Test suite for AH (Always in History) operator functionality
#
"""Test suite for AH operator parsing and conversion to EP form.

This module tests the AH temporal operator functionality including:
- Basic parsing of AH formulas
- Conversion from AH(φ) to ¬EP(¬φ)
- Integration with other operators
- DLNF transformation correctness
"""

import pytest
from parser import parse, parse_and_dlnf
from parser.ast_nodes import Not, EP, Literal, And, Or, AH
from utils.logger import get_logger


class TestAHOperator:
    """Test cases for AH operator parsing and conversion."""

    def setup_method(self):
        """Initialize logger for each test method."""
        self.logger = get_logger()

    def test_basic_ah_parsing(self):
        """Test that AH formulas are parsed and converted to EP form."""
        # Test AH(p) converts to ¬EP(¬p)
        result = parse("AH(p)")
        assert isinstance(result, Not)
        assert isinstance(result.operand, EP)
        assert isinstance(result.operand.operand, Not)
        assert isinstance(result.operand.operand.operand, Literal)
        assert result.operand.operand.operand.name == "p"

    def test_ah_with_complex_operand(self):
        """Test AH with complex Boolean operands."""
        # Test AH(p & q) converts to ¬EP(¬(p & q))
        result = parse("AH(p & q)")
        assert isinstance(result, Not)
        assert isinstance(result.operand, EP)
        assert isinstance(result.operand.operand, Not)
        assert isinstance(result.operand.operand.operand, And)

    def test_ah_with_disjunction(self):
        """Test AH with disjunction operand."""
        # Test AH(p | q) converts to ¬EP(¬(p | q))
        result = parse("AH(p | q)")
        assert isinstance(result, Not)
        assert isinstance(result.operand, EP)
        assert isinstance(result.operand.operand, Not)
        assert isinstance(result.operand.operand.operand, Or)

    def test_nested_ah(self):
        """Test nested AH operators."""
        # Test AH(AH(p))
        result = parse("AH(AH(p))")
        # This will be converted to ¬EP(¬(¬EP(¬p)))
        assert isinstance(result, Not)
        assert isinstance(result.operand, EP)

    def test_ah_with_negation(self):
        """Test AH with negated operand."""
        # Test AH(!p) converts to ¬EP(¬(!p)) = ¬EP(¬¬p) = ¬EP(p)
        result = parse("AH(!p)")
        assert isinstance(result, Not)
        assert isinstance(result.operand, EP)
        # Double negation should be eliminated: ¬¬p → p
        assert isinstance(result.operand.operand, Literal)
        assert result.operand.operand.name == "p"

    def test_ah_and_ep_combination(self):
        """Test combination of AH and EP operators."""
        # Test AH(p) & EP(q)
        result = parse("AH(p) & EP(q)")
        assert isinstance(result, And)
        # Left side: ¬EP(¬p)
        assert isinstance(result.left, Not)
        assert isinstance(result.left.operand, EP)
        # Right side: EP(q)
        assert isinstance(result.right, EP)

    def test_ah_dlnf_transformation(self):
        """Test DLNF transformation of AH formulas."""
        # Test that AH formulas are properly transformed in DLNF
        result = parse_and_dlnf("AH(p | q)")
        # AH(p | q) = ¬EP(¬(p | q)) = ¬EP(!p & !q)
        # After DLNF, EP distributes over disjunction
        assert isinstance(result, Not)

    def test_complex_ah_formula(self):
        """Test complex formula with multiple AH operators."""
        # Test (AH(p) | AH(q)) & EP(r)
        result = parse("(AH(p) | AH(q)) & EP(r)")
        assert isinstance(result, And)
        assert isinstance(result.left, Or)
        assert isinstance(result.right, EP)


class TestAHConversionValidation:
    """Test cases for validating AH to EP conversion correctness."""

    def setup_method(self):
        """Initialize logger for each test method."""
        self.logger = get_logger()

    def test_conversion_equivalence_simple(self):
        """Test that AH(p) is equivalent to ¬EP(¬p)."""
        # Parse AH(p)
        ah_formula = parse("AH(p)")

        # Parse the equivalent ¬EP(¬p) directly
        ep_formula = parse("!EP(!p)")

        # Both should have the same structure
        assert str(ah_formula) == str(ep_formula)

    def test_conversion_equivalence_complex(self):
        """Test conversion equivalence for complex formulas."""
        # Test AH(p & q) = ¬EP(¬(p & q))
        # Both should convert to the same DLNF form
        ah_dlnf = parse_and_dlnf("AH(p & q)")
        ep_dlnf = parse_and_dlnf("!EP(!(p & q))")

        # Both should produce the same DLNF structure
        assert str(ah_dlnf) == str(ep_dlnf)

    def test_de_morgan_laws_with_ah(self):
        """Test De Morgan's laws apply correctly with AH."""
        # AH(p & q) should be equivalent to ¬EP(!p | !q) after expansion
        ah_formula = parse("AH(p & q)")
        # The formula is ¬EP(¬(p & q))
        assert isinstance(ah_formula, Not)
        assert isinstance(ah_formula.operand, EP)

    def test_ah_true_and_false(self):
        """Test AH with Boolean constants."""
        # AH(true) should convert to ¬EP(¬true) = ¬EP(false)
        result_true = parse("AH(true)")
        assert isinstance(result_true, Not)
        assert isinstance(result_true.operand, EP)
        assert isinstance(result_true.operand.operand, Not)
        assert result_true.operand.operand.operand.name == "true"

        # AH(false) should convert to ¬EP(¬false) = ¬EP(true)
        result_false = parse("AH(false)")
        assert isinstance(result_false, Not)
        assert isinstance(result_false.operand, EP)
        assert isinstance(result_false.operand.operand, Not)
        assert result_false.operand.operand.operand.name == "false"

    def test_multiple_ah_operators(self):
        """Test formulas with multiple AH operators."""
        # Test AH(p) & AH(q)
        result = parse("AH(p) & AH(q)")
        assert isinstance(result, And)
        # Both sides should be ¬EP(¬...)
        assert isinstance(result.left, Not)
        assert isinstance(result.left.operand, EP)
        assert isinstance(result.right, Not)
        assert isinstance(result.right.operand, EP)

    def test_ah_precedence(self):
        """Test operator precedence with AH."""
        # Test AH(p) | q & r - should parse as AH(p) | (q & r)
        result = parse("AH(p) | q & r")
        assert isinstance(result, Or)
        assert isinstance(result.left, Not)  # AH(p) converted to ¬EP(¬p)
        assert isinstance(result.right, And)  # q & r

    def test_parenthesized_ah(self):
        """Test parentheses with AH operator."""
        # Test (AH(p))
        result = parse("(AH(p))")
        assert isinstance(result, Not)
        assert isinstance(result.operand, EP)

        # Test ((AH(p)))
        result = parse("((AH(p)))")
        assert isinstance(result, Not)
        assert isinstance(result.operand, EP)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
