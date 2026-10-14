"""Read-only machine observations for PC Guardian AI.

Network requests are disabled unless explicitly selected by the caller.
"""

from .system import collect_snapshot
from .windows import get_spooler_status

__all__ = ["collect_snapshot", "get_spooler_status"]
