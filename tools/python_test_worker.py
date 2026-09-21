"""Run discovered unittest identities with cooperative interruption on every platform."""
import os
import signal
import sys
import unittest

if __name__ == "__main__":
    if os.name == "nt":
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    try:
        unittest.main(module=None, argv=[sys.argv[0], "-v", *sys.argv[1:]])
    except KeyboardInterrupt:
        sys.exit(130)
