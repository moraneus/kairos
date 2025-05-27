# parser/exceptions.py

"""
Domain-specific exceptions for the PBTL parser.
"""


class ParseError(RuntimeError):
    """Raised when the input formula is syntactically invalid."""
