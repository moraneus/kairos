# parser/lexer.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Lexical analyzer for PBTL formula tokenization using SLY

"""Lexical analyzer for PBTL formula strings.

This module implements tokenization of Past-Based Temporal Logic formulas,
breaking input strings into tokens for parser consumption. The lexer handles
operator recognition, keyword distinction, and identifier processing while
providing meaningful error messages for invalid characters.

Supported Tokens:
- Operators: !, &, |, (, )
- Keywords: EP, true, false
- Identifiers: propositional variables
- Whitespace: ignored during tokenization
"""

from sly import Lexer
from utils.logger import get_logger


class PBTLLexer(Lexer):
    """SLY-based lexer for PBTL formula tokenization.

    Transforms input formula strings into token sequences for parsing.
    Distinguishes between reserved keywords and user-defined identifiers
    while handling operator precedence through token classification.

    Attributes:
        tokens: Set of valid token types
        ignore: Characters to skip during tokenization
        ID: Identifier pattern with keyword mapping
    """

    # Valid token types for parser recognition
    tokens = {
        "EP",
        "TRUE",
        "FALSE",
        "ID",
        "NOT",
        "AND",
        "OR",
        "LPAREN",
        "RPAREN",
    }

    # Whitespace characters to ignore
    ignore = " \t\r\n"

    # Operator and punctuation tokens
    NOT = r"!"
    AND = r"&"
    OR = r"\|"
    LPAREN = r"\("
    RPAREN = r"\)"

    # Identifier pattern: starts with letter/underscore, followed by alphanumerics/underscores
    ID = r"[a-zA-Z_][a-zA-Z0-9_]*"

    # Keyword mapping: reassign token types for reserved words
    ID["EP"] = "EP"
    ID["true"] = "TRUE"
    ID["false"] = "FALSE"

    def error(self, t):
        """Handle illegal characters during tokenization.

        Called automatically when encountering characters that don't match
        any defined token patterns. Advances past the problematic character
        and raises an informative error.

        Args:
            t: SLY token object containing error context

        Raises:
            ValueError: Always raised with character and position information
        """
        logger = get_logger()

        illegal_char = t.value[0]
        error_pos = self.index

        logger.debug(f"Illegal character '{illegal_char}' at position {error_pos}")

        # Skip the illegal character
        self.index += 1

        raise ValueError(
            f"Illegal character '{illegal_char}' encountered at position {error_pos}"
        )
