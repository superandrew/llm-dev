import os
import tempfile
import unittest

from llmdev.registry import BACKENDS, RegistryError, Model, load, get


class TestRegistry(unittest.TestCase):
    def _write_toml(self, content: str) -> str:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        path = os.path.join(tmpdir.name, "models.toml")
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_load_valid_file_with_two_models(self):
        toml = """
[defaults]
host = "192.168.1.1"

[models.qwen-coder-next]
backend = "ollama"
model = "qwen3-coder-next"
ctx = 65536
port = 11434
notes = "Current Aider worker."

[models.llama-model]
backend = "llama"
model = "~/models/gguf/model.gguf"
ctx = 32768
port = 8080
args = ["-ngl", "99"]
"""
        path = self._write_toml(toml)
        registry = load(path)

        self.assertEqual(len(registry), 2)

        model1 = registry["qwen-coder-next"]
        self.assertEqual(model1.name, "qwen-coder-next")
        self.assertEqual(model1.backend, "ollama")
        self.assertEqual(model1.model, "qwen3-coder-next")
        self.assertEqual(model1.ctx, 65536)
        self.assertEqual(model1.port, 11434)
        self.assertEqual(model1.host, "192.168.1.1")
        self.assertEqual(model1.args, ())
        self.assertEqual(model1.env, ())
        self.assertEqual(model1.notes, "Current Aider worker.")

        model2 = registry["llama-model"]
        self.assertEqual(model2.name, "llama-model")
        self.assertEqual(model2.backend, "llama")
        self.assertEqual(model2.model, os.path.expanduser("~/models/gguf/model.gguf"))
        self.assertEqual(model2.ctx, 32768)
        self.assertEqual(model2.port, 8080)
        self.assertEqual(model2.host, "192.168.1.1")
        self.assertEqual(model2.args, ("-ngl", "99"))
        self.assertEqual(model2.env, ())
        self.assertEqual(model2.notes, "")

    def test_host_default_and_override(self):
        toml = """
[defaults]
host = "10.0.0.1"

[models.test]
backend = "ollama"
model = "test"
ctx = 4096
port = 1234
host = "10.0.0.2"
"""
        path = self._write_toml(toml)
        registry = load(path)
        model = registry["test"]
        self.assertEqual(model.host, "10.0.0.2")

    def test_args_default_empty_tuple(self):
        toml = """
[models.test]
backend = "ollama"
model = "test"
ctx = 4096
port = 1234
"""
        path = self._write_toml(toml)
        registry = load(path)
        model = registry["test"]
        self.assertEqual(model.args, ())

    def test_env_sorted_tuple(self):
        toml = """
[models.test]
backend = "ollama"
model = "test"
ctx = 4096
port = 1234
env = { KEY_B = "val2", KEY_A = "val1" }
"""
        path = self._write_toml(toml)
        registry = load(path)
        model = registry["test"]
        self.assertEqual(model.env, (("KEY_A", "val1"), ("KEY_B", "val2")))

    def test_missing_ctx(self):
        toml = """
[models.test]
backend = "ollama"
model = "test"
port = 1234
"""
        path = self._write_toml(toml)
        with self.assertRaises(RegistryError) as cm:
            load(path)
        self.assertIn("models.test: missing required key 'ctx'", str(cm.exception))

    def test_bad_backend(self):
        toml = """
[models.test]
backend = "invalid"
model = "test"
ctx = 4096
port = 1234
"""
        path = self._write_toml(toml)
        with self.assertRaises(RegistryError) as cm:
            load(path)
        self.assertIn("models.test: invalid backend 'invalid'", str(cm.exception))

    def test_port_out_of_range(self):
        toml = """
[models.test]
backend = "ollama"
model = "test"
ctx = 4096
port = 70000
"""
        path = self._write_toml(toml)
        with self.assertRaises(RegistryError) as cm:
            load(path)
        self.assertIn("models.test: port must be an integer between 1 and 65535", str(cm.exception))

    def test_unknown_key(self):
        toml = """
[models.test]
backend = "ollama"
model = "test"
ctx = 4096
port = 1234
unknown_key = "value"
"""
        path = self._write_toml(toml)
        with self.assertRaises(RegistryError) as cm:
            load(path)
        self.assertIn("models.test: unknown key(s): unknown_key", str(cm.exception))

    def test_tilde_expanded_for_llama(self):
        toml = """
[models.test]
backend = "llama"
model = "~/models/gguf/model.gguf"
ctx = 4096
port = 8080
"""
        path = self._write_toml(toml)
        registry = load(path)
        model = registry["test"]
        self.assertEqual(model.model, os.path.expanduser("~/models/gguf/model.gguf"))

    def test_tilde_not_expanded_for_ollama(self):
        toml = """
[models.test]
backend = "ollama"
model = "~/models/gguf/model.gguf"
ctx = 4096
port = 11434
"""
        path = self._write_toml(toml)
        registry = load(path)
        model = registry["test"]
        self.assertEqual(model.model, "~/models/gguf/model.gguf")

    def test_empty_registry_raises_error(self):
        toml = """
[defaults]
host = "127.0.0.1"
"""
        path = self._write_toml(toml)
        with self.assertRaises(RegistryError) as cm:
            load(path)
        self.assertIn("no models defined", str(cm.exception))

    def test_get_unknown_name_lists_available_names(self):
        toml = """
[models.model-a]
backend = "ollama"
model = "a"
ctx = 4096
port = 1234

[models.model-b]
backend = "ollama"
model = "b"
ctx = 4096
port = 1234
"""
        path = self._write_toml(toml)
        registry = load(path)
        with self.assertRaises(RegistryError) as cm:
            get(registry, "unknown")
        self.assertIn("unknown model 'unknown'. Available: model-a, model-b", str(cm.exception))

    def test_get_returns_model(self):
        toml = """
[models.test]
backend = "ollama"
model = "test"
ctx = 4096
port = 1234
"""
        path = self._write_toml(toml)
        registry = load(path)
        model = get(registry, "test")
        self.assertIsInstance(model, Model)
        self.assertEqual(model.name, "test")

    def test_ctx_true_rejected(self):
        toml = """
[models.test]
backend = "ollama"
model = "test"
ctx = true
port = 1234
"""
        path = self._write_toml(toml)
        with self.assertRaises(RegistryError) as cm:
            load(path)
        self.assertIn("models.test: ctx must be a positive integer", str(cm.exception))
