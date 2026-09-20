import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

from workflow_runner.runner import (
    build_runtime_config,
    normalize_model_name,
    selected_model,
)


class WorkflowRunnerCliTests(unittest.TestCase):
    def test_module_entrypoint_usage(self):
        result = subprocess.run(
            [sys.executable, "-m", "workflow_runner"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stderr or result.stdout)

    def test_litellm_model_aliases(self):
        self.assertEqual(normalize_model_name("claude-opus-4.8"), "anthropic/claude-opus-4-1-20250805")
        self.assertEqual(normalize_model_name("haiku-4.5"), "anthropic/claude-3-5-haiku-latest")
        self.assertEqual(normalize_model_name("copilot-gpt-4.1"), "openai/gpt-4.1")
        self.assertEqual(normalize_model_name("local-model"), "openai/local-model")

    def test_runtime_examples_for_copilot_and_lm_studio(self):
        with mock.patch.dict(
            os.environ,
            {
                "GENAI_PROVIDER": "copilot",
                "OPENAI_API_KEY": "copilot-key",
                "OPENAI_API_BASE": "https://api.githubcopilot.com",
            },
            clear=False,
        ):
            self.assertEqual(build_runtime_config("copilot-gpt-4.1")["api_base"], "https://api.githubcopilot.com")

        with mock.patch.dict(
            os.environ,
            {
                "GENAI_PROVIDER": "openai",
                "OPENAI_API_KEY": "lm-studio-key",
                "OPENAI_API_BASE": "http://localhost:1234/v1",
            },
            clear=False,
        ):
            self.assertEqual(build_runtime_config("local-model")["api_base"], "http://localhost:1234/v1")

        with mock.patch.dict(
            os.environ,
            {
                "GENAI_PROVIDER": "copilot",
                "OPENAI_API_KEY": "copilot-key",
                "OPENAI_API_BASE": "https://api.githubcopilot.com",
            },
            clear=False,
        ):
            config = build_runtime_config("github-copilot/claude-opus-4.8")
            self.assertEqual(config["provider"], "copilot")
            self.assertEqual(config["model"], "github-copilot/claude-opus-4.8")
            self.assertEqual(config["api_base"], "https://api.githubcopilot.com")

    def test_model_is_selected_without_cli_model(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(selected_model("ocr", ""), "claude-opus-4.8")

        with mock.patch.dict(os.environ, {"NOTARYMIND_OCR_MODEL": "haiku 4.5"}, clear=True):
            self.assertEqual(selected_model("ocr", ""), "haiku 4.5")

    def test_ocr_environment_model_is_used_by_runtime_config(self):
        with mock.patch.dict(
            os.environ,
            {
                "NOTARYMIND_OCR_MODEL": "github-copilot/claude-opus-4.8",
                "NOTARYMIND_GENAI_MODEL": "gpt-4o-mini",
                "GENAI_PROVIDER": "copilot",
                "OPENAI_API_KEY": "copilot-key",
                "OPENAI_API_BASE": "https://api.githubcopilot.com",
            },
            clear=True,
        ):
            model = selected_model("ocr", "")
            config = build_runtime_config(model)

        self.assertEqual(model, "github-copilot/claude-opus-4.8")
        self.assertEqual(config["provider"], "copilot")
        self.assertEqual(config["model"], "github-copilot/claude-opus-4.8")


if __name__ == "__main__":
    unittest.main()
