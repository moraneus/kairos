# parser/__init__.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Formula parsing and transformation components for temporal logic expressions

"""PBTL formula parsing and normalization for runtime verification.

This module provides comprehensive parsing and transformation capabilities for
Past-Based Temporal Logic (PBTL) formulas. The parsing pipeline converts textual
formula representations into abstract syntax trees and subsequently transforms
them into Disjunctive Literal Normal Form (DLNF) suitable for efficient runtime
monitoring algorithms.

The transformation process ensures that temporal formulas are optimized for
the monitoring algorithms described in the runtime verification literature,
particularly for distributed systems with partial order semantics.

Core Functions:
    parse: Converts formula strings into Abstract Syntax Trees
    parse_and_dlnf: Complete parsing and DLNF transformation pipeline

Supported Logic:
    - Past-Based Temporal Logic (PBTL) operators
    - Boolean connectives (AND, OR, NOT)
    - Temporal operators (EP - "Exists in Past")
    - Propositional variables and constants

Grammar Features:
    - Left-associative binary operators
    - Proper operator precedence handling
    - Parenthetical grouping support
    - Error recovery and meaningful error messages

Example:
    >>> from parser import parse_and_dlnf
    >>> ast = parse_and_dlnf("EP(EP(p) & !EP(q))")
    >>> # Returns DLNF-transformed AST ready for monitoring
"""

from .exceptions import ParseError
from .grammar import _PBTLParser
from .dlnf_transformer import DLNFTransformer
from utils.logger import get_logger


def parse(source: str):
    """Parse PBTL formula string into Abstract Syntax Tree representation.

    Converts a textual formula representation into a structured AST that preserves
    the logical structure and operator relationships. Uses a fresh parser instance
    for each invocation to ensure stateless operation and thread safety.

    The parser implements a complete PBTL grammar with proper precedence rules
    and supports complex nested expressions with parenthetical grouping.

    Args:
        source: Well-formed PBTL formula string to parse

    Returns:
        Root AST node representing the parsed formula structure

    Raises:
        ParseError: Formula syntax is malformed or contains unsupported constructs

    Example:
        >>> ast = parse("EP(p & q)")
        >>> # Returns EP node with And node containing Literal nodes
    """
    logger = get_logger()
    logger.debug(f"Parsing formula: {source}")

    parser = _PBTLParser()

    try:
        result = parser.parse(source)
        logger.debug(
            f"Formula parsed successfully into AST with type: {type(result).__name__}"
        )
        return result

    except ParseError:
        logger.debug("ParseError encountered during formula parsing")
        raise

    except Exception as exc:
        logger.debug(f"Unexpected parsing error: {type(exc).__name__}: {exc}")
        raise ParseError(str(exc)) from exc


def parse_and_dlnf(source: str):
    """Parse formula string and transform to Disjunctive Literal Normal Form.

    Provides a complete processing pipeline that parses the input formula and
    immediately applies DLNF transformation. This canonical form is optimized
    for runtime verification algorithms and enables efficient property monitoring
    over distributed system executions.

    The DLNF transformation distributes temporal operators over disjunctions
    and ensures that the resulting formula structure matches the monitoring
    algorithm requirements described in the runtime verification literature.

    The transformation may result in a Directed Acyclic Graph (DAG) structure
    where common subformulas are shared, providing both space efficiency and
    computational optimization during monitoring.

    Args:
        source: Well-formed PBTL formula string to parse and transform

    Returns:
        Root AST node of the DLNF-transformed formula structure

    Raises:
        ParseError: Formula parsing or transformation fails

    Example:
        >>> dlnf_ast = parse_and_dlnf("EP(p | q)")
        >>> # Returns Or node with EP(p) and EP(q) as children
    """
    logger = get_logger()
    logger.debug(f"Parsing and transforming formula to DLNF: {source}")

    # Parse formula into initial AST
    ast = parse(source)
    logger.debug("Initial parsing completed, beginning DLNF transformation")

    # Transform to DLNF canonical form
    transformer = DLNFTransformer()
    dlnf_result = transformer.transform(ast)

    logger.debug(
        f"DLNF transformation completed, result type: {type(dlnf_result).__name__}"
    )
    return dlnf_result


__all__ = ["parse", "parse_and_dlnf", "ParseError"]

__version__ = "1.0.0"
__author__ = "Moran Omer"
__description__ = "PBTL formula parsing and DLNF transformation components"
