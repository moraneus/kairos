# parser/lexer.py

"""
Lexer for PBTL concrete syntax, built with SLY.

This lexer identifies tokens for the PBTL language. It correctly distinguishes
between reserved keywords (EP, true, false) and generic identifiers, and
raises an error for any illegal characters.
"""

from sly import Lexer


class PBTLLexer(Lexer):
    # Set of token names. These are the valid types a token can have.
    tokens = {
        "EP", "TRUE", "FALSE", "ID",
        "NOT", "AND", "OR", "LPAREN", "RPAREN",
    }

    # Characters to be ignored by the lexer (e.g., whitespace, tabs, newlines).
    ignore = " \t\r\n"

    # --- Operators and Punctuation (defined by simple regular expressions) ---
    NOT    = r"!"
    AND    = r"&"
    OR     = r"\|"
    LPAREN = r"\("
    RPAREN = r"\)"

    # --- Identifiers and Keywords ---
    # The 'ID' token is defined first using a general regex for identifiers.
    ID = r"[a-zA-Z_][a-zA-Z0-9_]*"

    # The SLY lexer provides a special dictionary on the ID token to handle
    # reserved keywords. If a matched ID's text is a key in this dictionary,
    # its token type is reassigned to the corresponding value.
    # The values must be the string names of the tokens.
    ID['EP'] = "EP"
    ID['true'] = "TRUE"
    ID['false'] = "FALSE"

    def error(self, t):
        """
        Handles any character that doesn't match a defined token.
        This method is called by SLY when it encounters an illegal character.
        """
        self.index += 1
        raise ValueError(f"Illegal character {t.value!r} at position {self.index}")
