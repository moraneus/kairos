# core/verdict.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Verdict enumeration for runtime verification monitoring results

from enum import Enum, auto
from utils.logger import get_logger


class Verdict(Enum):
    """Three-valued logic result for PBTL property monitoring.

    Represents the possible outcomes of runtime verification analysis for
    temporal logic properties over distributed system executions. The three-valued
    logic accommodates the inherent uncertainty in monitoring partial traces
    where complete system information may not be available.

    This enumeration provides the foundation for verdict propagation and
    combination in complex formula evaluation, supporting both definitive
    conclusions and inconclusive states that may require additional observation.

    Values:
        TRUE: Property is definitively satisfied by the observed execution
        FALSE: Property is definitively violated by the observed execution
        UNKNOWN: Verdict cannot be determined from available information
    """

    TRUE = auto()
    FALSE = auto()
    UNKNOWN = auto()

    def __str__(self) -> str:
        """Generate string representation of the verdict.

        Returns:
            Human-readable verdict name (TRUE, FALSE, or UNKNOWN)
        """
        return self.name

    def is_conclusive(self) -> bool:
        """Determine if this verdict represents a definitive monitoring result.

        Conclusive verdicts (TRUE or FALSE) indicate that sufficient information
        has been observed to make a definitive determination about property
        satisfaction. Inconclusive verdicts (UNKNOWN) suggest that additional
        system observation may be required or that the property cannot be
        determined from the available trace information.

        This distinction is crucial for runtime verification systems that need
        to decide whether to continue monitoring or can terminate analysis
        based on definitive property violation or satisfaction.

        Returns:
            True if verdict is definitive (TRUE or FALSE), False if inconclusive
        """
        logger = get_logger()
        is_conclusive = self in (Verdict.TRUE, Verdict.FALSE)

        logger.debug(
            f"Verdict {self.name} is {'conclusive' if is_conclusive else 'inconclusive'}"
        )

        return is_conclusive

    def combine_disjunctive(self, other: "Verdict") -> "Verdict":
        """Combine this verdict with another using disjunctive (OR) semantics.

        Implements the truth table for disjunctive combination of three-valued
        logic verdicts, as required for evaluating disjunctive temporal formulas
        where any satisfied disjunct makes the entire formula true.

        Combination rules:
        - TRUE OR anything = TRUE
        - FALSE OR TRUE = TRUE
        - FALSE OR FALSE = FALSE
        - FALSE OR UNKNOWN = UNKNOWN
        - UNKNOWN OR UNKNOWN = UNKNOWN

        Args:
            other: Verdict to combine with this verdict

        Returns:
            Combined verdict following disjunctive semantics
        """
        logger = get_logger()
        logger.debug(f"Combining verdicts disjunctively: {self.name} OR {other.name}")

        if self == Verdict.TRUE or other == Verdict.TRUE:
            result = Verdict.TRUE
        elif self == Verdict.FALSE and other == Verdict.FALSE:
            result = Verdict.FALSE
        else:
            result = Verdict.UNKNOWN

        logger.debug(f"Disjunctive combination result: {result.name}")
        return result

    def combine_conjunctive(self, other: "Verdict") -> "Verdict":
        """Combine this verdict with another using conjunctive (AND) semantics.

        Implements the truth table for conjunctive combination of three-valued
        logic verdicts, as required for evaluating conjunctive temporal formulas
        where all conjuncts must be satisfied for the formula to be true.

        Combination rules:
        - FALSE AND anything = FALSE
        - TRUE AND FALSE = FALSE
        - TRUE AND TRUE = TRUE
        - TRUE AND UNKNOWN = UNKNOWN
        - UNKNOWN AND UNKNOWN = UNKNOWN

        Args:
            other: Verdict to combine with this verdict

        Returns:
            Combined verdict following conjunctive semantics
        """
        logger = get_logger()
        logger.debug(f"Combining verdicts conjunctively: {self.name} AND {other.name}")

        if self == Verdict.FALSE or other == Verdict.FALSE:
            result = Verdict.FALSE
        elif self == Verdict.TRUE and other == Verdict.TRUE:
            result = Verdict.TRUE
        else:
            result = Verdict.UNKNOWN

        logger.debug(f"Conjunctive combination result: {result.name}")
        return result

    def negate(self) -> "Verdict":
        """Compute the logical negation of this verdict.

        Implements three-valued logic negation where definitive verdicts
        are swapped and inconclusive verdicts remain inconclusive.

        Negation rules:
        - NOT TRUE = FALSE
        - NOT FALSE = TRUE
        - NOT UNKNOWN = UNKNOWN

        Returns:
            Negated verdict
        """
        logger = get_logger()
        logger.debug(f"Negating verdict: NOT {self.name}")

        if self == Verdict.TRUE:
            result = Verdict.FALSE
        elif self == Verdict.FALSE:
            result = Verdict.TRUE
        else:
            result = Verdict.UNKNOWN

        logger.debug(f"Negation result: {result.name}")
        return result
