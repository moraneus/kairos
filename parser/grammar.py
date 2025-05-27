# parser/grammar.py

"""
PBTL grammar definition using SLY.

Defines an LALR(1) parser that builds AST nodes for Past-Based Temporal Logic (PBTL).
Operator precedence (lowest → highest):
    OR   ‘|’
    AND  ‘&’
    NOT  ‘!’  (unary)
    EP         (unary keyword)
    grouping via ‘( … )’

Each production returns an instance of our AST node classes.
"""

from sly import Parser

from .lexer import PBTLLexer
from .ast_nodes import Expr, Literal, Not, And, Or, EP
from .exceptions import ParseError


class _PBTLParser(Parser):
    tokens = PBTLLexer.tokens

    precedence = (
        ("left", "OR"),
        ("left", "AND"),
        ("right", "NOT"),
    )

    @_('expr')
    def start(self, p) -> Expr:
        return p.expr

    @_('EP LPAREN expr RPAREN')
    def expr(self, p) -> Expr:
        return EP(p.expr)

    @_('NOT expr')
    def expr(self, p) -> Expr:
        return Not(p.expr)

    @_('expr AND expr')
    def expr(self, p) -> Expr:
        return And(p.expr0, p.expr1)

    @_('expr OR expr')
    def expr(self, p) -> Expr:
        return Or(p.expr0, p.expr1)

    @_('LPAREN expr RPAREN')
    def expr(self, p) -> Expr:
        return p.expr

    @_('literal')
    def expr(self, p) -> Expr:
        return p.literal

    @_('ID')
    def literal(self, p) -> Literal:
        return Literal(p.ID)

    @_('TRUE')
    def literal(self, p) -> Literal:
        return Literal("true")

    @_('FALSE')
    def literal(self, p) -> Literal:
        return Literal("false")

    def parse(self, text: str) -> Expr:
        """
        Parse the given text into a PBTL AST. Raises ParseError on failure.
        """
        ast = super().parse(PBTLLexer().tokenize(text))
        if ast is None:
            raise ParseError("empty formula")
        return ast

    def error(self, token):
        raise ParseError(f"Syntax error near {token.value!r}")
