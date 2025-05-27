# parser/dlnf_transformer.py

"""
DLNF transformer for PBTL ASTs.

Rewrites any `EP(φ ∨ ψ)` into `EP(φ) ∨ EP(ψ)` and ensures
that no `Or` appears inside the operand of an `EP`.  Internally
converts Boolean subformulas to Disjunctive Normal Form (DNF)
so that each `EP` wraps a conjunction.
"""

from __future__ import annotations
from typing import Dict, Tuple, List
from . import ast_nodes as ast


def _to_dnf(expr: ast.Expr) -> Tuple[Tuple[ast.Expr, ...], ...]:
    """
    Convert a propositional expression into DNF.

    Returns a tuple of conjunctions, each conjunction itself
    represented as a tuple of atomic factors (literals, EPs, or their negations).
    """
    # Base cases: treat Literals and EP nodes as atomic units.
    if isinstance(expr, (ast.Literal, ast.EP)):
        return ((expr,),)
    if isinstance(expr, ast.Not) and isinstance(expr.operand, (ast.Literal, ast.EP)):
        return ((expr,),)

    # Disjunction: combine the DNFs of both sides
    if isinstance(expr, ast.Or):
        left_dnf = _to_dnf(expr.left)
        right_dnf = _to_dnf(expr.right)
        return left_dnf + right_dnf

    # Conjunction: distribute to form all combinations of left and right clauses
    if isinstance(expr, ast.And):
        left_clauses = _to_dnf(expr.left)
        right_clauses = _to_dnf(expr.right)
        # Cartesian product of clauses
        return tuple(left + right for left in left_clauses for right in right_clauses)

    # Negation of a compound expression: apply De Morgan's laws
    if isinstance(expr, ast.Not):
        inner = expr.operand
        # De Morgan for Or: !(A | B) -> !A & !B
        if isinstance(inner, ast.Or):
            return _to_dnf(ast.And(ast.Not(inner.left), ast.Not(inner.right)))
        # De Morgan for And: !(A & B) -> !A | !B
        if isinstance(inner, ast.And):
            return _to_dnf(ast.Or(ast.Not(inner.left), ast.Not(inner.right)))
        # Double Negation: !!A -> A
        if isinstance(inner, ast.Not):
            return _to_dnf(inner.operand)

    # Fallback: treat any other expression type as a single atomic factor.
    return ((expr,),)


class DLNFTransformer(ast.Visitor):
    """
    Visitor that transforms a PBTL AST into Disjunctive Literal Normal Form (DLNF).

    After transformation, the entire formula is in DNF, and no `Or` appears
    under any `EP` node.
    """

    def __init__(self):
        self._memo: Dict[ast.Expr, ast.Expr] = {}

    def transform(self, root: ast.Expr) -> ast.Expr:
        """Return a DLNF-equivalent AST, sharing common subexpressions."""
        self._memo.clear()

        # Phase 1: Recursively transform the tree from the bottom up.
        visited_ast = self._visit(root)

        # Phase 2: Convert the entire simplified result into DNF.
        clauses = _to_dnf(visited_ast)
        if not clauses:
            return ast.Literal("false")

        return _build_or([_build_and(clause) for clause in clauses])

    def _visit(self, node: ast.Expr) -> ast.Expr:
        if node in self._memo:
            return self._memo[node]

        result = node.accept(self)

        self._memo[node] = result
        return result

    def visit_literal(self, n: ast.Literal) -> ast.Literal:
        return n

    def visit_not(self, n: ast.Not) -> ast.Expr:
        operand = self._visit(n.operand)
        if isinstance(operand, ast.Not):
            return operand.operand
        return ast.Not(operand)

    def visit_and(self, n: ast.And) -> ast.And:
        return ast.And(self._visit(n.left), self._visit(n.right))

    def visit_or(self, n: ast.Or) -> ast.Or:
        return ast.Or(self._visit(n.left), self._visit(n.right))

    def visit_ep(self, n: ast.EP) -> ast.Expr:
        """
        Transform EP(φ) by first rewriting φ into DNF, then
        distributing EP over each DNF clause.
        """
        operand = self._visit(n.operand)
        clauses = _to_dnf(operand)
        if not clauses:
            return ast.EP(ast.Literal("false"))

        ep_terms = [ast.EP(_build_and(clause)) for clause in clauses]
        return _build_or(ep_terms)


def _build_and(factors: Tuple[ast.Expr, ...]) -> ast.Expr:
    """Construct a left-associated conjunction from a sequence of factors."""
    if not factors:
        return ast.Literal("true")
    expr = factors[0]
    for f in factors[1:]:
        expr = ast.And(expr, f)
    return expr


def _build_or(terms: List[ast.Expr]) -> ast.Expr:
    """Construct a left-associated disjunction from a list of terms."""
    if not terms:
        return ast.Literal("false")
    expr = terms[0]
    for t in terms[1:]:
        expr = ast.Or(expr, t)
    return expr
