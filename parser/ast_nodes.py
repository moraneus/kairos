# parser/ast_nodes.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Abstract Syntax Tree node classes for temporal logic formula representation

"""AST node classes for representing parsed PBTL formulas.

This module defines immutable and hashable node classes used to construct tree
representations of Past-Based Temporal Logic (PBTL) formulas. The AST supports
standard Boolean connectives and the EP temporal operator for expressing
properties over distributed system executions.

Node Types:
    Literal: Propositional variables and Boolean constants
    Not, And, Or: Standard Boolean connectives
    EP: "Exists in Past" temporal operator

All nodes support the visitor design pattern for traversal and transformation.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol


class Visitor(Protocol):
    """Interface for AST visitors implementing the visitor design pattern.

    Concrete visitors must implement visit methods for each AST node type
    to enable type-safe traversal and transformation operations.
    """

    def visit_literal(self, n: Literal): ...

    def visit_not(self, n: Not): ...

    def visit_and(self, n: And): ...

    def visit_or(self, n: Or): ...

    def visit_ep(self, n: EP): ...


@dataclass(frozen=True, slots=True)
class Expr:
    """Base class for all AST nodes in temporal logic formulas.

    Provides the foundation for immutable expression trees with visitor pattern
    support. All concrete node types inherit from this class and must implement
    the accept method for visitor dispatch and __str__ for string representation.
    """

    def accept(self, v: Visitor):
        """Dispatch to the appropriate visitor method.

        Enables the visitor pattern by calling the correct visit_* method
        on the provided visitor instance based on the concrete node type.

        Args:
            v: Visitor instance to process this node

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError

    def __str__(self) -> str:
        """Return string representation of the AST node.

        Provides a human-readable representation that typically corresponds
        to the original formula syntax.

        Returns:
            String representation of the node

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class Literal(Expr):
    """Atomic proposition or Boolean constant in a formula.

    Represents leaf nodes in the AST tree, including propositional variables
    (e.g., "p", "ready") and Boolean constants ("true", "false").

    Attributes:
        name: The identifier string for this literal
    """

    name: str

    def accept(self, v: Visitor):
        """Accept visitor and dispatch to visit_literal method.

        Args:
            v: Visitor instance to process this literal

        Returns:
            Result of visitor's visit_literal method
        """
        return v.visit_literal(self)

    def __str__(self) -> str:
        """Return the literal name as string representation.

        Returns:
            The name attribute of this literal
        """
        return self.name


@dataclass(frozen=True, slots=True)
class Not(Expr):
    """Logical negation operator for Boolean expressions.

    Represents the unary negation operation that inverts the truth value
    of its operand expression.

    Attributes:
        operand: The expression being negated
    """

    operand: Expr

    def accept(self, v: Visitor):
        """Accept visitor and dispatch to visit_not method.

        Args:
            v: Visitor instance to process this negation

        Returns:
            Result of visitor's visit_not method
        """
        return v.visit_not(self)

    def __str__(self) -> str:
        """Return string representation of negation.

        Returns:
            Formatted string with negation operator and operand
        """
        return f"!{self.operand}"


@dataclass(frozen=True, slots=True)
class And(Expr):
    """Logical conjunction operator for Boolean expressions.

    Represents the binary AND operation that is true when both
    operands are true.

    Attributes:
        left: Left operand of the conjunction
        right: Right operand of the conjunction
    """

    left: Expr
    right: Expr

    def accept(self, v: Visitor):
        """Accept visitor and dispatch to visit_and method.

        Args:
            v: Visitor instance to process this conjunction

        Returns:
            Result of visitor's visit_and method
        """
        return v.visit_and(self)

    def __str__(self) -> str:
        """Return string representation of conjunction.

        Returns:
            Formatted string with both operands and AND operator
        """
        return f"({self.left} & {self.right})"


@dataclass(frozen=True, slots=True)
class Or(Expr):
    """Logical disjunction operator for Boolean expressions.

    Represents the binary OR operation that is true when at least
    one operand is true.

    Attributes:
        left: Left operand of the disjunction
        right: Right operand of the disjunction
    """

    left: Expr
    right: Expr

    def accept(self, v: Visitor):
        """Accept visitor and dispatch to visit_or method.

        Args:
            v: Visitor instance to process this disjunction

        Returns:
            Result of visitor's visit_or method
        """
        return v.visit_or(self)

    def __str__(self) -> str:
        """Return string representation of disjunction.

        Returns:
            Formatted string with both operands and OR operator
        """
        return f"({self.left} | {self.right})"


@dataclass(frozen=True, slots=True)
class EP(Expr):
    """Temporal operator "Exists in Past" for PBTL formulas.

    Asserts that the operand formula was true at some point in the past
    along at least one execution path. This is the primary temporal operator
    in Past-Based Temporal Logic.

    Attributes:
        operand: The formula whose past satisfaction is asserted
    """

    operand: Expr

    def accept(self, v: Visitor):
        """Accept visitor and dispatch to visit_ep method.

        Args:
            v: Visitor instance to process this EP operator

        Returns:
            Result of visitor's visit_ep method
        """
        return v.visit_ep(self)

    def __str__(self) -> str:
        """Return string representation of EP operator.

        Returns:
            Formatted string with EP keyword and operand
        """
        return f"EP({self.operand})"
