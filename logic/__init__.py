# logic/__init__.py

"""Core runtime-monitor interface.

This package provides:
  • Monitor: incremental partial-order property monitor
  • Verdict: tri-state outcome (TRUE, FALSE, INCONCLUSIVE)
  • PropertyAndTraceMonitor: CLI-style runner for a property + CSV trace
  • TraceFormatError: raised on spec/trace parse errors
"""

from .monitor import Monitor
from .runner import PropertyAndTraceMonitor, TraceFormatError
from .verdict import Verdict

__all__ = [
    "Monitor",
    "Verdict",
    "PropertyAndTraceMonitor",
    "TraceFormatError",
]
