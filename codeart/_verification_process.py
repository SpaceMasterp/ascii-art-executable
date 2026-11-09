"""Compatibility imports for callers using the former E-specific module."""

from .procutil import (
    BuildFailed,
    BuildSession,
    CommandTimedOut,
    CompilerInfo,
    DependencyUnavailable,
    VerificationContext,
    WorkStopped,
    check_context,
    run_command,
    _stop_process,
)
