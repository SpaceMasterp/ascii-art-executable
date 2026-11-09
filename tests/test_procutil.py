"""Preserve the old process-module imports during the public-module migration."""

from codeart import procutil
from codeart import _verification_process as legacy
from codeart.verify import VerificationContext


def test_legacy_process_imports_keep_type_identity():
    assert legacy.BuildSession is procutil.BuildSession
    assert legacy.WorkStopped is procutil.WorkStopped
    assert legacy.run_command is procutil.run_command
    assert legacy.VerificationContext is VerificationContext
    assert legacy._stop_process is procutil.stop_process
