"""Basic tests for model-link discovery; no installed models required."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import importlib.util

CODE = Path(__file__).resolve().parents[1] / "scripts" / "refresh-model-links.py"
spec = importlib.util.spec_from_file_location("refresh_model_links", CODE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ModelLinkTests(unittest.TestCase):
    def test_basic_and_multimodal_reuse(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            source = root / "source"
            source.mkdir()
            (source / "small.gguf").write_bytes(b"model")
            sub = source / "model-with-projector"
            sub.mkdir()
            (sub / "vision.gguf").write_bytes(b"model")
            (sub / "mmproj-F16.gguf").write_bytes(b"projector")
            (source / "mmproj-standalone.gguf").write_bytes(b"bad")
            destination = root / "catalogue"
            self.assertEqual(module.refresh(destination, [source]), 2)
            self.assertTrue((destination / "small.gguf").is_symlink())
            self.assertEqual((destination / "small.gguf").read_bytes(), b"model")
            self.assertTrue((destination / "vision" / "vision.gguf").is_symlink())
            self.assertTrue((destination / "vision" / "mmproj-F16.gguf").is_symlink())
            self.assertFalse((destination / "mmproj-standalone.gguf").exists())
            self.assertEqual(module.refresh(destination, [source]), 2)
            self.assertEqual((source / "small.gguf").read_bytes(), b"model")


if __name__ == "__main__":
    unittest.main()
