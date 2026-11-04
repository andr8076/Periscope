"""Offline unit tests; no Jan installation or web server required."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from periscope.core import (
    as_openwebui_chat, linked_imports, load_state, locate_thread,
    read_thread, save_state, thread_dirs, PeriscopeError,
)


class PeriscopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "Jan/data"
        folder = self.data / "threads" / "jan_001"
        folder.mkdir(parents=True)
        (folder / "thread.json").write_text(json.dumps({
            "id": "jan_001", "title": "My local chat", "model": {"id": "my.gguf"},
        }))
        (folder / "messages.jsonl").write_text(
            json.dumps({"id": "m1", "role": "user", "content": [{"type": "text", "text": {"value": "Hello"}}], "created_at": 1700000000000}) + "\n" +
            json.dumps({"id": "m2", "role": "assistant", "content": [{"type": "text", "text": {"value": "Hello back"}}], "created_at": 1700000001000}) + "\n" +
            json.dumps({"id": "m3", "role": "tool", "content": "private tool data"}) + "\n"
        )
        self.folder = folder

    def test_read_and_history(self):
        chat = as_openwebui_chat(read_thread(self.folder))
        self.assertEqual(chat["title"], "My local chat")
        self.assertEqual(chat["models"], ["my.gguf"])
        self.assertEqual(len(chat["messages"]), 2)
        first, second = chat["messages"]
        self.assertEqual(first["timestamp"], 1700000000)
        self.assertEqual(first["childrenIds"], [second["id"]])
        self.assertEqual(second["parentId"], first["id"])
        self.assertEqual(chat["history"]["currentId"], second["id"])

    def test_select_only_linked(self):
        state = {"version": 1, "links": {"jan_001": {"openwebui_id": None}}}
        output = linked_imports(self.data, state)
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["meta"]["periscope"]["jan_thread_id"], "jan_001")
        self.assertEqual(linked_imports(self.data, {"version": 1, "links": {}}), [])

    def test_state_roundtrip_private(self):
        state = {"version": 1, "links": {"jan_001": {"openwebui_id": "web-002"}}}
        folder = self.root / "registry"
        save_state(folder, state)
        self.assertEqual(load_state(folder), state)
        self.assertEqual((folder / "links.json").stat().st_mode & 0o777, 0o600)

    def test_paths_not_traversable(self):
        with self.assertRaises(PeriscopeError):
            locate_thread(self.data, "../outside")

    def test_read_only_source(self):
        before = (self.folder / "messages.jsonl").read_bytes()
        as_openwebui_chat(read_thread(self.folder))
        self.assertEqual((self.folder / "messages.jsonl").read_bytes(), before)

    def test_no_partial_missing_thread(self):
        other = self.data / "threads" / "partial"
        other.mkdir()
        self.assertEqual(len(thread_dirs(self.data)), 1)


if __name__ == "__main__":
    unittest.main()
