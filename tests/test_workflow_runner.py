import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

from workflow_runner.runner import (
    ProjectLock,
    RunnerError,
    build_runtime_config,
    selected_model,
)
from workflow_runner.tasks.ocr_task import run_ocr
from workflow_runner.tasks.interpret_task import run_interpret
from workflow_runner.tasks.map_task import run_map


class WorkflowRunnerCliTests(unittest.TestCase):
    def test_script_entrypoint_usage(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "workflow_runner/runner.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stderr or result.stdout)

    def test_model_names_are_passed_through_verbatim(self):
        with mock.patch.dict(os.environ, {"GENAI_PROVIDER": "anthropic"}, clear=True):
            self.assertEqual(build_runtime_config("claude-opus-4.8")["model"], "claude-opus-4.8")

        with mock.patch.dict(os.environ, {"GENAI_PROVIDER": "copilot"}, clear=True):
            self.assertEqual(build_runtime_config(" github-copilot/haiku-4.5 ")["model"], "github-copilot/haiku-4.5")

        with mock.patch.dict(os.environ, {"GENAI_PROVIDER": "openai"}, clear=True):
            self.assertEqual(build_runtime_config(" local-model ")["model"], "local-model")

    def test_runtime_examples_for_copilot_and_lm_studio(self):
        with mock.patch.dict(
            os.environ,
            {
                "GENAI_PROVIDER": "copilot",
                "GITHUB_COPILOT_API_BASE": "https://api.githubcopilot.com",
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
                "GITHUB_COPILOT_API_BASE": "https://api.githubcopilot.com",
            },
            clear=False,
        ):
            config = build_runtime_config("github_copilot/claude-opus-4.8")
            self.assertEqual(config["provider"], "copilot")
            self.assertEqual(config["model"], "github_copilot/claude-opus-4.8")
            self.assertEqual(config["api_base"], "https://api.githubcopilot.com")
            self.assertEqual(config["api_key_name"], "")

    def test_runtime_examples_for_azure_vertex_bedrock_and_ollama(self):
        with mock.patch.dict(
            os.environ,
            {
                "GENAI_PROVIDER": "azure",
                "AZURE_API_KEY": "azure-key",
                "AZURE_API_BASE": "https://example.openai.azure.com",
                "AZURE_API_VERSION": "2024-10-21",
            },
            clear=False,
        ):
            config = build_runtime_config("gpt-4.1")
            self.assertEqual(config["provider"], "azure")
            self.assertEqual(config["model"], "gpt-4.1")
            self.assertEqual(config["api_key_name"], "AZURE_API_KEY")
            self.assertEqual(config["request_kwargs"]["api_version"], "2024-10-21")

        with mock.patch.dict(
            os.environ,
            {
                "GENAI_PROVIDER": "vertex_ai",
                "VERTEXAI_PROJECT": "demo-project",
                "VERTEXAI_LOCATION": "us-central1",
            },
            clear=True,
        ):
            config = build_runtime_config("gemini-2.0-flash")
            self.assertEqual(config["provider"], "vertex_ai")
            self.assertEqual(config["model"], "gemini-2.0-flash")
            self.assertEqual(config["request_kwargs"]["vertex_project"], "demo-project")
            self.assertEqual(config["request_kwargs"]["vertex_location"], "us-central1")

        with mock.patch.dict(
            os.environ,
            {
                "GENAI_PROVIDER": "bedrock",
                "AWS_REGION": "us-east-1",
            },
            clear=True,
        ):
            config = build_runtime_config("anthropic.claude-3-5-sonnet-20241022-v2:0")
            self.assertEqual(config["provider"], "bedrock")
            self.assertEqual(config["model"], "anthropic.claude-3-5-sonnet-20241022-v2:0")
            self.assertEqual(config["request_kwargs"]["aws_region_name"], "us-east-1")

        with mock.patch.dict(
            os.environ,
            {
                "GENAI_PROVIDER": "ollama",
            },
            clear=True,
        ):
            config = build_runtime_config("llama3.1:8b")
            self.assertEqual(config["provider"], "ollama")
            self.assertEqual(config["model"], "llama3.1:8b")
            self.assertEqual(config["api_base"], "http://localhost:11434")

    def test_model_is_selected_without_cli_model(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(selected_model("ocr", ""), "github_copilot/claude-opus-4.8")

        with mock.patch.dict(os.environ, {"NOTARYMIND_OCR_MODEL": "haiku 4.5"}, clear=True):
            self.assertEqual(selected_model("ocr", ""), "haiku 4.5")

    def test_ocr_environment_model_is_used_by_runtime_config(self):
        with mock.patch.dict(
            os.environ,
            {
                "NOTARYMIND_OCR_MODEL": "github_copilot/claude-opus-4.8",
                "NOTARYMIND_GENAI_MODEL": "gpt-4o-mini",
                "GENAI_PROVIDER": "copilot",
                "GITHUB_COPILOT_API_BASE": "https://api.githubcopilot.com",
            },
            clear=True,
        ):
            model = selected_model("ocr", "")
            config = build_runtime_config(model)

        self.assertEqual(model, "github_copilot/claude-opus-4.8")
        self.assertEqual(config["provider"], "copilot")
        self.assertEqual(config["model"], "github_copilot/claude-opus-4.8")

    def test_task_modules_expose_run_entrypoints(self):
        self.assertTrue(callable(run_ocr))
        self.assertTrue(callable(run_interpret))
        self.assertTrue(callable(run_map))

    def test_project_lock_error_mentions_project_and_lock_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "demo-project"
            project.mkdir()
            lock = ProjectLock(project)
            lock.path.write_text(f'{{"pid": {os.getpid()}}}', encoding="utf-8")

            with self.assertRaises(RunnerError) as ctx:
                with lock:
                    pass

            message = str(ctx.exception)
            self.assertIn("demo-project", message)
            self.assertIn(str(project), message)
            self.assertIn(str(lock.path), message)
            self.assertNotIn("Project is already being processed: tmp", message)

    def test_project_lock_reaps_stale_file_without_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock = ProjectLock(project)
            lock.path.write_text("", encoding="utf-8")
            with lock:
                self.assertTrue(lock.path.exists())
                self.assertFalse(project.joinpath(".workflow_runner.lock").exists())
            self.assertFalse(lock.path.exists())

    def test_project_lock_rejects_running_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            lock = ProjectLock(project)
            lock.path.write_text('{"pid": %d}' % os.getpid(), encoding="utf-8")
            with self.assertRaises(RunnerError):
                with lock:
                    self.fail("lock should not be acquired while current pid owns it")


if __name__ == "__main__":
    unittest.main()
