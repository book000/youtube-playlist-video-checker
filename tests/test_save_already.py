import json
import os
import tempfile
import unittest
from unittest import mock

for _key in ("GOOGLE_TOKEN", "DISCORD_TOKEN", "DISCORD_CHANNEL_ID"):
    os.environ.setdefault(_key, "dummy")

from src import __main__ as app

PREVIOUS = {"playlist": ["old1"]}
UPDATED = {"playlist": ["old1", "new1"]}


class TestSaveAlready(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        original = os.getcwd()
        self.addCleanup(os.chdir, original)
        os.chdir(directory.name)

    def write_previous(self):
        with open("already.json", "w") as f:
            json.dump(PREVIOUS, f)

    def read_state(self):
        with open("already.json", "r") as f:
            return json.load(f)

    def test_save_writes_state_and_leaves_no_temporary_file(self):
        self.write_previous()

        app.save_already(UPDATED)

        self.assertEqual(UPDATED, self.read_state())
        self.assertEqual(["already.json"], os.listdir("."))

    def assert_failure_keeps_previous_state(self, target, name):
        self.write_previous()

        with (
            mock.patch(target, side_effect=OSError("boom")),
            self.assertRaises(OSError),
        ):
            app.save_already(UPDATED)

        self.assertEqual(PREVIOUS, self.read_state(), name)
        self.assertEqual(["already.json"], os.listdir("."), name)

    def test_json_dump_failure_keeps_previous_state(self):
        self.assert_failure_keeps_previous_state("src.__main__.json.dump", "dump")

    def test_fsync_failure_keeps_previous_state(self):
        self.assert_failure_keeps_previous_state("src.__main__.os.fsync", "fsync")

    def test_replace_failure_keeps_previous_state(self):
        self.assert_failure_keeps_previous_state("src.__main__.os.replace", "replace")
