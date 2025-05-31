# parser/exceptions.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Custom exceptions for formula parsing and transformation

"""Domain-specific exceptions for PBTL formula processing.

This module defines exceptions that can be raised during parsing and
transformation of Past-Based Temporal Logic formulas. All exceptions
inherit from appropriate base classes and provide meaningful error
information for debugging and user feedback.
"""


class ParseError(RuntimeError):
    """Exception raised when formula parsing fails due to syntax errors.

    Indicates that the input formula does not conform to the PBTL grammar
    or contains other structural errors that prevent successful parsing.
    Used throughout the parsing pipeline to provide consistent error handling.
    """

    pass
