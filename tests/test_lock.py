"""Cron lock: flock on a file next to the script, released by the kernel on exit."""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from _env import HAS_FCNTL, ROOT, ba

TESTS_DIR = Path(__file__).resolve().parent


class LockLocationTests(unittest.TestCase):
    def test_lock_lives_next_to_the_script_not_in_tmp(self):
        self.assertEqual(os.path.dirname(ba.LOCK_FILE), os.path.dirname(os.path.abspath(ba.__file__)))
        self.assertEqual(os.path.dirname(ba.LOCK_FILE), str(ROOT))
        self.assertFalse(ba.LOCK_FILE.startswith("/tmp"))


@unittest.skipUnless(HAS_FCNTL, "fcntl.flock only exists on POSIX (production is Linux)")
class FlockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lock_path = os.path.join(self.tmp.name, ".blog_automation.lock")
        patcher = mock.patch.object(ba, "LOCK_FILE", self.lock_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self._release)

    def _release(self):
        if ba._lock_fd is not None:
            os.close(ba._lock_fd)
            ba._lock_fd = None

    def test_second_run_is_refused_while_the_first_holds_the_lock(self):
        self.assertTrue(ba.acquire_lock())
        first_fd = ba._lock_fd
        with self.assertLogs(ba.log, level="WARNING"):
            self.assertFalse(ba.acquire_lock())
        self.assertEqual(ba._lock_fd, first_fd)
        self.assertEqual(os.stat(self.lock_path).st_mode & 0o777, 0o600)

    def test_lock_is_released_when_the_holder_crashes(self):
        child = textwrap.dedent(
            f"""
            import os, sys
            sys.path.insert(0, {str(TESTS_DIR)!r})
            from _env import ba
            ba.LOCK_FILE = {self.lock_path!r}
            assert ba.acquire_lock()
            os._exit(3)  # simulated crash: no cleanup code runs
            """
        )
        result = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertTrue(os.path.exists(self.lock_path))  # stale file left behind...
        self.assertTrue(ba.acquire_lock())  # ...but the lock is free

    def test_symlinked_lock_file_is_not_followed(self):
        target = os.path.join(self.tmp.name, "victim")
        with open(target, "w") as f:
            f.write("keep")
        os.symlink(target, self.lock_path)
        with self.assertRaises(OSError):
            ba.acquire_lock()
        with open(target) as f:
            self.assertEqual(f.read(), "keep")


if __name__ == "__main__":
    unittest.main()
