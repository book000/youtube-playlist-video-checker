import fcntl
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

for _key in ("GOOGLE_TOKEN", "DISCORD_TOKEN", "DISCORD_CHANNEL_ID"):
    os.environ.setdefault(_key, "dummy")

from src import __main__ as app

LOGGER_NAME = "youtube-playlist-video-checker"
ALREADY_RUNNING = "Another instance is already running; exiting"

HOLD_LOCK_SCRIPT = """
import fcntl, sys
f = open("already.json.lock", "a")
fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
print("locked", flush=True)
sys.stdin.readline()
"""


class TestSingleInstanceLock(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        original = os.getcwd()
        self.addCleanup(os.chdir, original)
        os.chdir(directory.name)

    def hold_lock_in_subprocess(self):
        process = subprocess.Popen(
            [sys.executable, "-c", HOLD_LOCK_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(process.stdout.close)
        self.addCleanup(process.wait)
        self.addCleanup(process.stdin.close)
        self.assertEqual("locked\n", process.stdout.readline())
        return process

    def run_main_expecting_exit(self):
        with (
            mock.patch.object(app, "check_playlists") as check_playlists,
            self.assertLogs(LOGGER_NAME, "ERROR") as logs,
            self.assertRaises(SystemExit) as raised,
        ):
            app.main()
        return raised.exception.code, logs.records, check_playlists

    def test_main_exits_when_lock_is_held_by_another_descriptor(self):
        with open(app.LOCK_PATH, "a") as holder:
            fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, records, check_playlists = self.run_main_expecting_exit()

        self.assertEqual(1, code)
        self.assertEqual([ALREADY_RUNNING], [r.getMessage() for r in records])
        check_playlists.assert_not_called()

    def test_main_runs_when_no_other_holder(self):
        with mock.patch.object(app, "check_playlists", return_value=True) as run:
            app.main()

        run.assert_called_once_with()

    def test_lock_can_be_taken_again_after_release(self):
        with app.single_instance_lock():
            pass
        with app.single_instance_lock():
            pass

    def test_lock_is_released_when_body_raises(self):
        with self.assertRaises(RuntimeError), app.single_instance_lock():
            raise RuntimeError("body failed")
        with app.single_instance_lock():
            pass

    def test_competing_process_blocks_main_until_it_releases_the_lock(self):
        process = self.hold_lock_in_subprocess()

        code, records, check_playlists = self.run_main_expecting_exit()

        self.assertEqual(1, code)
        self.assertEqual([ALREADY_RUNNING], [r.getMessage() for r in records])
        check_playlists.assert_not_called()

        process.stdin.write("\n")
        process.stdin.flush()
        process.wait()
        with mock.patch.object(app, "check_playlists", return_value=True) as run:
            app.main()
        run.assert_called_once_with()

    def test_lock_acquisition_error_is_reported_and_exits(self):
        with mock.patch.object(app.fcntl, "flock", side_effect=OSError("no locks")):
            code, records, check_playlists = self.run_main_expecting_exit()

        self.assertEqual(1, code)
        self.assertEqual(
            ["Cannot acquire the instance lock: no locks"],
            [r.getMessage() for r in records],
        )
        check_playlists.assert_not_called()

    def test_lock_file_open_error_is_reported_and_exits(self):
        with mock.patch.object(app, "open", side_effect=OSError("denied"), create=True):
            code, records, check_playlists = self.run_main_expecting_exit()

        self.assertEqual(1, code)
        self.assertEqual(
            ["Cannot acquire the instance lock: denied"],
            [r.getMessage() for r in records],
        )
        check_playlists.assert_not_called()

    def test_os_error_in_body_is_not_reported_as_a_lock_error(self):
        with (
            mock.patch.object(app, "check_playlists", side_effect=OSError("disk")),
            self.assertRaises(OSError) as raised,
        ):
            app.main()

        self.assertEqual("disk", str(raised.exception))
