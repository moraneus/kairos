# logic/formula.py

"""
Encapsulates a property formula in Disjunctive Literal Normal Form (DLNF).

After parsing and DLNF conversion, the AST’s root is either an Or node
or a single EP node, ready for runtime monitoring.
"""

from dataclasses import dataclass
from parser.ast_nodes import Expr


@dataclass(frozen=True)
class Formula:
    """
    Wraps the root of a DLNF AST.

    Attributes:
        root: The top-level expression in DLNF (Or or EP).
    """
    root: Expr
