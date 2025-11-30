# parser/ah_rewriter.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# AH operator rewriting using De Morgan's laws and logical equivalences
#
"""Simple AH operator conversion to EP form.

This module implements the basic AH to EP conversion: AH(φ) ≡ ¬EP(¬φ)
This is the standard definition from Past-Based Temporal Logic (PaBTL).
"""

from . import ast_nodes as ast


class AHRewriter(ast.Visitor):
    """Converts AH formulas to equivalent ¬EP(¬φ) form.

    Implements the basic PaBTL definition: AH(φ) ≡ ¬EP(¬φ)
    """

    def rewrite(self, node: ast.Expr) -> ast.Expr:
        """Convert AH operators in an AST node.

        Args:
            node: AST node to convert

        Returns:
            AST node with AH operators converted to ¬EP(¬φ) form
        """
        return node.accept(self)

    def visit_literal(self, n: ast.Literal) -> ast.Literal:
        """Literals remain unchanged."""
        return n

    def visit_not(self, n: ast.Not) -> ast.Expr:
        """Handle negation nodes."""
        operand = n.operand.accept(self)

        # ¬¬φ → φ (double negation elimination)
        if isinstance(operand, ast.Not):
            return operand.operand

        return ast.Not(operand)

    def visit_and(self, n: ast.And) -> ast.Expr:
        """Handle conjunction."""
        left = n.left.accept(self)
        right = n.right.accept(self)
        return ast.And(left, right)

    def visit_or(self, n: ast.Or) -> ast.Expr:
        """Handle disjunction."""
        left = n.left.accept(self)
        right = n.right.accept(self)
        return ast.Or(left, right)

    def visit_ep(self, n: ast.EP) -> ast.EP:
        """EP operators are preserved but their operands are rewritten."""
        return ast.EP(n.operand.accept(self))

    def visit_ah(self, n: ast.AH) -> ast.Expr:
        """Convert AH to ¬EP(¬φ) using the basic definition.

        AH(φ) ≡ ¬EP(¬φ) for all formulas φ.

        Special case:
        - AH(¬φ) → ¬EP(φ) (eliminates double negation)
        """
        operand = n.operand

        # Special case: AH(¬φ) → ¬EP(¬¬φ) → ¬EP(φ)
        if isinstance(operand, ast.Not):
            return ast.Not(ast.EP(operand.operand))

        # Standard case: AH(φ) → ¬EP(¬φ)
        return ast.Not(ast.EP(ast.Not(operand)))
