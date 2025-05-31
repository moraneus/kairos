# parser/grammar.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# LALR(1) grammar and parser for PBTL formulas using SLY

"""PBTL grammar implementation using SLY parser generator.

This module defines the grammar rules and parsing logic for Past-Based Temporal Logic
formulas. The parser constructs Abstract Syntax Trees from token streams provided
by the lexer, handling operator precedence and associativity correctly.

Grammar Features:
- Standard Boolean operators (AND, OR, NOT) with proper precedence
- EP temporal operator with functional notation
- Parenthetical grouping for precedence override
- Comprehensive error handling with meaningful messages

Operator Precedence (lowest to highest):
- OR ('|'): left-associative
- AND ('&'): left-associative
- NOT ('!'): right-associative
- EP: handled by grammar structure
"""

from sly import Parser
from .lexer import PBTLLexer
from .ast_nodes import Expr, Literal, Not, And, Or, EP
from .exceptions import ParseError
from utils.logger import get_logger


class _PBTLParser(Parser):
    """SLY-based LALR(1) parser for PBTL formulas.

    Implements grammar rules to construct AST nodes from token streams.
    Handles precedence, associativity, and provides detailed error reporting
    for malformed formulas.

    Attributes:
        tokens: Token types from PBTLLexer
        precedence: Operator precedence and associativity rules
    """

    tokens = PBTLLexer.tokens

    precedence = (
        ("left", "OR"),
        ("left", "AND"),
        ("right", "NOT"),
    )

    @_("expr")
    def start(self, p) -> Expr:
        """Start rule: complete formula is a single expression."""
        return p.expr

    # Expression grammar rules
    @_("EP LPAREN expr RPAREN")
    def expr(self, p) -> Expr:
        """EP temporal operator with parenthesized operand."""
        return EP(p.expr)

    @_("NOT expr")
    def expr(self, p) -> Expr:
        """Negation operator."""
        return Not(p.expr)

    @_("expr AND expr")
    def expr(self, p) -> Expr:
        """Conjunction operator."""
        return And(p.expr0, p.expr1)

    @_("expr OR expr")
    def expr(self, p) -> Expr:
        """Disjunction operator."""
        return Or(p.expr0, p.expr1)

    @_("LPAREN expr RPAREN")
    def expr(self, p) -> Expr:
        """Parenthesized expression for grouping."""
        return p.expr

    @_("literal")
    def expr(self, p) -> Expr:
        """Expression can be a single literal."""
        return p.literal

    # Literal grammar rules
    @_("ID")
    def literal(self, p) -> Literal:
        """Identifier as propositional variable."""
        return Literal(p.ID)

    @_("TRUE")
    def literal(self, p) -> Literal:
        """Boolean constant true."""
        return Literal("true")

    @_("FALSE")
    def literal(self, p) -> Literal:
        """Boolean constant false."""
        return Literal("false")

    def parse(self, text: str) -> Expr:
        """Parse PBTL formula text into AST.

        Tokenizes the input text and constructs an Abstract Syntax Tree
        representing the formula structure. Handles empty formulas and
        provides meaningful error messages for syntax errors.

        Args:
            text: PBTL formula string to parse

        Returns:
            Root AST node representing the parsed formula

        Raises:
            ParseError: If formula is empty or contains syntax errors
        """
        logger = get_logger()
        logger.debug(f"Parsing formula: {text}")

        try:
            ast_result = super().parse(PBTLLexer().tokenize(text))

            if ast_result is None and text.strip() == "":
                raise ParseError("Input formula is empty.")

            if ast_result is None:
                raise ParseError("Failed to parse formula (syntax error).")

            logger.debug(
                f"Successfully parsed formula into {type(ast_result).__name__}"
            )
            return ast_result

        except ParseError:
            logger.debug("Parse error encountered")
            raise
        except Exception as e:
            logger.debug(f"Unexpected parsing error: {e}")
            raise ParseError(f"Parse failed: {e}")

    def error(self, token):
        """Handle syntax errors during parsing.

        Called automatically by SLY when encountering tokens that don't
        match any grammar rule. Provides detailed error information
        including token position and type.

        Args:
            token: Problematic token or None for EOF errors

        Raises:
            ParseError: Always raises with detailed error information
        """
        if token:
            error_msg = (
                f"Syntax error near '{token.value}' "
                f"(type: {token.type}) at line {token.lineno}, position {token.index}"
            )
        else:
            error_msg = "Syntax error: Unexpected end of formula"

        raise ParseError(error_msg)
