"""Compatibility imports for callers using the former E-specific module."""

from .procutil import (
    BuildFailed,
    BuildSession,
    CommandTimedOut,
    CompilerInfo,
    DependencyUnavailable,
    WorkStopped,
    check_context,
    run_command,
    stop_process as _stop_process,
)
from .verify import VerificationContext
