# parser/__init__.py

"""
Public API for parsing PBTL formulas and converting them to
Disjunctive Lower Normal Form (DLNF) for monitoring.
"""

from .exceptions import ParseError
from .grammar import _PBTLParser
from .dlnf_transformer import DLNFTransformer


def parse(source: str):
    """
    Parse a PBTL formula from *source* into its abstract syntax tree (AST).

    Raises:
        ParseError: if the text is not a well-formed PBTL formula.
    """
    parser = _PBTLParser()  # sly Parser is stateful; build a fresh one
    try:
        return parser.parse(source)
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(str(exc)) from exc


def parse_and_dlnf(source: str):
    """
    Parse a PBTL formula and immediately convert its AST into DLNF.

    Returns a DAG-structured AST where repeated sub-formulas are shared.
    """
    ast = parse(source)
    return DLNFTransformer().transform(ast)


__all__ = ["parse", "parse_and_dlnf"]
