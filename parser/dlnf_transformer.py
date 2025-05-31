# parser/dlnf_transformer.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# AST transformer for Disjunctive Literal Normal Form conversion

"""Transforms Abstract Syntax Trees into Disjunctive Literal Normal Form (DLNF).

This module implements the DLNF transformation required for efficient PBTL monitoring.
The key transformation distributes EP operators over disjunctions: EP(φ ∨ ψ) becomes
EP(φ) ∨ EP(ψ). This ensures that no Or nodes appear directly within EP operands,
creating a canonical form suitable for the monitoring algorithm.

The transformation process:
1. Converts Boolean subformulas to Disjunctive Normal Form (DNF)
2. Distributes EP operators over disjunctions
3. Applies Boolean simplifications (double negation, De Morgan's laws)
"""

from __future__ import annotations
from typing import Dict, Tuple, List
from . import ast_nodes as ast
from utils.logger import get_logger


class DLNFTransformer(ast.Visitor):
    """Transforms parsed AST into Disjunctive Literal Normal Form.

    Uses the visitor pattern to traverse and transform the AST while maintaining
    memoization for efficiency. The resulting DLNF structure enables direct
    application of the PBTL monitoring algorithm.

    Attributes:
        _memo: Cache for transformed subexpressions to avoid redundant computation
    """

    def __init__(self):
        """Initialize transformer with empty memoization cache."""
        self._memo: Dict[ast.Expr, ast.Expr] = {}

    def transform(self, root: ast.Expr) -> ast.Expr:
        """Transform the AST into DLNF.

        Performs a two-phase transformation:
        1. Bottom-up traversal with EP distribution and Boolean simplification
        2. Top-level DNF conversion to ensure disjunctive structure

        Args:
            root: Root node of the AST to transform

        Returns:
            Transformed AST in DLNF
        """
        logger = get_logger()
        logger.debug(f"Starting DLNF transformation of {type(root).__name__}")

        self._memo.clear()

        # Phase 1: Recursive transformation with EP distribution
        visited_ast = self._visit(root)

        # Phase 2: Ensure top-level DNF structure
        clauses = _to_dnf(visited_ast)
        if not clauses:
            result = ast.Literal("false")
        else:
            result = _build_or([_build_and(clause) for clause in clauses])

        logger.debug(f"DLNF transformation complete: {type(result).__name__}")
        return result

    def _visit(self, node: ast.Expr) -> ast.Expr:
        """Visit AST node with memoization.

        Args:
            node: Node to visit and transform

        Returns:
            Transformed node
        """
        if node in self._memo:
            return self._memo[node]

        result = node.accept(self)
        self._memo[node] = result
        return result

    def visit_literal(self, n: ast.Literal) -> ast.Literal:
        """Visit literal node (no transformation needed).

        Args:
            n: Literal node

        Returns:
            The same literal node
        """
        return n

    def visit_not(self, n: ast.Not) -> ast.Expr:
        """Visit negation node with double negation simplification.

        Args:
            n: Negation node

        Returns:
            Transformed negation or simplified expression
        """
        operand = self._visit(n.operand)

        # Simplify double negation: !!A -> A
        if isinstance(operand, ast.Not):
            return operand.operand

        return ast.Not(operand)

    def visit_and(self, n: ast.And) -> ast.And:
        """Visit conjunction node.

        Args:
            n: Conjunction node

        Returns:
            Conjunction with transformed operands
        """
        return ast.And(self._visit(n.left), self._visit(n.right))

    def visit_or(self, n: ast.Or) -> ast.Or:
        """Visit disjunction node.

        Args:
            n: Disjunction node

        Returns:
            Disjunction with transformed operands
        """
        return ast.Or(self._visit(n.left), self._visit(n.right))

    def visit_ep(self, n: ast.EP) -> ast.Expr:
        """Visit EP node with distribution over disjunctions.

        This is the core DLNF transformation: EP(φ ∨ ψ) becomes EP(φ) ∨ EP(ψ).
        The operand is converted to DNF and EP is distributed over each clause.

        Args:
            n: EP node

        Returns:
            Transformed EP expression as disjunction of EP terms
        """
        logger = get_logger()
        logger.debug(f"Transforming EP node with operand: {type(n.operand).__name__}")

        operand = self._visit(n.operand)
        clauses = _to_dnf(operand)

        if not clauses:
            return ast.EP(ast.Literal("false"))

        ep_terms = [ast.EP(_build_and(clause)) for clause in clauses]
        logger.debug(f"EP distribution created {len(ep_terms)} disjuncts")

        return _build_or(ep_terms)


def _to_dnf(expr: ast.Expr) -> Tuple[Tuple[ast.Expr, ...], ...]:
    """Convert expression to Disjunctive Normal Form.

    Transforms the expression into a tuple of clauses, where each clause
    is a tuple of atomic factors. Handles Boolean connectives using
    standard DNF conversion rules.

    Args:
        expr: Expression to convert

    Returns:
        Tuple of clauses representing the DNF
    """
    # Atomic expressions
    if isinstance(expr, (ast.Literal, ast.EP)):
        return ((expr,),)

    if isinstance(expr, ast.Not) and isinstance(expr.operand, (ast.Literal, ast.EP)):
        return ((expr,),)

    # Disjunction: combine clauses
    if isinstance(expr, ast.Or):
        left_dnf = _to_dnf(expr.left)
        right_dnf = _to_dnf(expr.right)
        return left_dnf + right_dnf

    # Conjunction: distribute clauses
    if isinstance(expr, ast.And):
        left_clauses = _to_dnf(expr.left)
        right_clauses = _to_dnf(expr.right)
        return tuple(
            left_clause + right_clause
            for left_clause in left_clauses
            for right_clause in right_clauses
        )

    # Negation: apply De Morgan's laws
    if isinstance(expr, ast.Not):
        inner = expr.operand

        # De Morgan: !(A | B) -> !A & !B
        if isinstance(inner, ast.Or):
            return _to_dnf(ast.And(ast.Not(inner.left), ast.Not(inner.right)))

        # De Morgan: !(A & B) -> !A | !B
        if isinstance(inner, ast.And):
            return _to_dnf(ast.Or(ast.Not(inner.left), ast.Not(inner.right)))

        # Double negation: !!A -> A
        if isinstance(inner, ast.Not):
            return _to_dnf(inner.operand)

    # Fallback for unrecognized expressions
    return ((expr,),)


def _build_and(factors: Tuple[ast.Expr, ...]) -> ast.Expr:
    """Build left-associative conjunction from factors.

    Args:
        factors: Tuple of expressions to conjoin

    Returns:
        Conjunction expression or 'true' if empty
    """
    if not factors:
        return ast.Literal("true")

    expr = factors[0]
    for factor in factors[1:]:
        expr = ast.And(expr, factor)
    return expr


def _build_or(terms: List[ast.Expr]) -> ast.Expr:
    """Build left-associative disjunction from terms.

    Args:
        terms: List of expressions to disjoin

    Returns:
        Disjunction expression or 'false' if empty
    """
    if not terms:
        return ast.Literal("false")

    expr = terms[0]
    for term in terms[1:]:
        expr = ast.Or(expr, term)
    return expr
