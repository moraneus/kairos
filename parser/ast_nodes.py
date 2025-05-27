# parser/ast_nodes.py

"""
Abstract Syntax Tree (AST) definitions for Past-Based Temporal Logic (PBTL).

This module defines immutable, hashable node classes for PBTL formulas:
  - Literal: propositional variables or Boolean constants.
  - Not, And, Or: Boolean connectives.
  - EP: “exists-in-past” temporal operator.

Each node supports a visitor pattern via `accept`, and `__str__` gives
round-trippable surface syntax.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol


class Visitor(Protocol):
    """Interface for AST visitors (one visit_* method per node type)."""

    def visit_literal(self, n: Literal): ...
    def visit_not(self, n: Not): ...
    def visit_and(self, n: And): ...
    def visit_or(self, n: Or): ...
    def visit_ep(self,   n: EP): ...


@dataclass(frozen=True, slots=True)
class Expr:
    """
    Base class for all PBTL AST nodes.
    Subclasses must implement `accept` and `__str__`.
    """

    def accept(self, v: Visitor):
        """Dispatch to the matching Visitor method."""
        raise NotImplementedError

    def __str__(self) -> str:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class Literal(Expr):
    """Atomic proposition or Boolean constant."""
    name: str

    def accept(self, v: Visitor):
        return v.visit_literal(self)

    def __str__(self):
        return self.name


@dataclass(frozen=True, slots=True)
class Not(Expr):
    """Logical negation."""
    operand: Expr

    def accept(self, v: Visitor):
        return v.visit_not(self)

    def __str__(self):
        return f"!{self.operand}"


@dataclass(frozen=True, slots=True)
class And(Expr):
    """Logical conjunction."""
    left: Expr
    right: Expr

    def accept(self, v: Visitor):
        return v.visit_and(self)

    def __str__(self):
        return f"({self.left} & {self.right})"


@dataclass(frozen=True, slots=True)
class Or(Expr):
    """Logical disjunction."""
    left: Expr
    right: Expr

    def accept(self, v: Visitor):
        return v.visit_or(self)

    def __str__(self):
        return f"({self.left} | {self.right})"


@dataclass(frozen=True, slots=True)
class EP(Expr):
    """Temporal operator EP φ: “φ held somewhere in the past”. """
    operand: Expr

    def accept(self, v: Visitor):
        return v.visit_ep(self)

    def __str__(self):
        return f"EP({self.operand})"
