import json
import os
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

from workflow_runner.common import build_run_summary
from workflow_runner.runner import (
    ProjectLock,
    RunnerError,
    build_runtime_config,
    selected_model,
)
from workflow_runner.tasks.ocr_task import render_pdf_pages_to_images, run_ocr
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
            self.assertEqual(build_runtime_config(" github_copilot/haiku-4.5 ")["model"], "github_copilot/haiku-4.5")

        with mock.patch.dict(os.environ, {"GENAI_PROVIDER": "openai"}, clear=True):
            self.assertEqual(build_runtime_config(" local-model ")["model"], "local-model")

    def test_runtime_examples_for_copilot_and_lm_studio(self):
        with mock.patch.dict(
            os.environ,
            {
                "GENAI_PROVIDER": "copilot",
                "GITHUB_COPILOT_API_BASE": "https://api.enterprise.githubcopilot.com",
            },
            clear=False,
        ):
            config = build_runtime_config("github_copilot/gpt-4.1")
            self.assertEqual(config["provider"], "github_copilot")
            self.assertEqual(config["api_base"], "https://api.enterprise.githubcopilot.com")

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
                "GITHUB_COPILOT_API_BASE": "https://api.enterprise.githubcopilot.com",
            },
            clear=False,
        ):
            config = build_runtime_config("github_copilot/claude-opus-4.8")
            self.assertEqual(config["provider"], "github_copilot")
            self.assertEqual(config["model"], "github_copilot/claude-opus-4.8")
            self.assertEqual(config["api_base"], "https://api.enterprise.githubcopilot.com")
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
                "GITHUB_COPILOT_API_BASE": "https://api.enterprise.githubcopilot.com",
            },
            clear=True,
        ):
            model = selected_model("ocr", "")
            config = build_runtime_config(model)

        self.assertEqual(model, "github_copilot/claude-opus-4.8")
        self.assertEqual(config["provider"], "github_copilot")
        self.assertEqual(config["model"], "github_copilot/claude-opus-4.8")

    def test_task_modules_expose_run_entrypoints(self):
        self.assertTrue(callable(run_ocr))
        self.assertTrue(callable(run_interpret))
        self.assertTrue(callable(run_map))

    def test_shared_run_summary_schema_is_consistent(self):
        payload = build_run_summary("ocr", model="gpt-test", processed=2, failed=[], files_written=["a.jpg", "b.jpg"])
        self.assertEqual(payload["operation"], "ocr")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["processed"], 2)
        self.assertEqual(payload["failed"], [])
        self.assertEqual(payload["files_written"], ["a.jpg", "b.jpg"])

    def test_ocr_only_new_processes_only_new_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "demo-project"
            (project / "imported").mkdir(parents=True)
            (project / "metadata").mkdir(parents=True)
            (project / "imported" / "old.jpg").write_text("old", encoding="utf-8")
            (project / "imported" / "new.jpg").write_text("new", encoding="utf-8")
            (project / "metadata" / "old.json").write_text(json.dumps({"image": "old.jpg", "full_transcript": "old transcript"}), encoding="utf-8")
            (project / "GLOSSARIO.md").write_text("# Glossary\n", encoding="utf-8")

            processed = []

            def fake_request(messages, model, image=None):
                processed.append(image.name if image else "noimage")
                return {
                    "image": image.name if image else "",
                    "document_type": "test",
                    "document_date": "2024",
                    "location": "",
                    "full_transcript": "text",
                    "entities": {"names": [], "dates": [], "places": [], "values": []},
                    "properties": [],
                    "persons": [],
                    "relations": [],
                    "ocr_metadata": {"status": "done", "notes": "ok"},
                }

            with mock.patch("workflow_runner.tasks.ocr_task._request_json", side_effect=fake_request):
                summary = run_ocr(project, "model-x", only_new=True)

        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["files_written"], ["new.jpg"])
        self.assertEqual(processed, ["new.jpg"])

    def test_interpret_only_new_reports_missing_metadata_for_new_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "demo-project"
            (project / "imported").mkdir(parents=True)
            (project / "metadata").mkdir(parents=True)
            (project / "imported" / "new-image.jpg").write_text("new", encoding="utf-8")
            (project / "GLOSSARIO.md").write_text("# Glossary\n", encoding="utf-8")

            summary = run_interpret(project, "model-x", only_new=True)

        self.assertEqual(summary["processed"], 0)
        self.assertEqual(summary["status"], "error")
        self.assertEqual(summary["failed"][0]["file"], "new-image.json")
        self.assertIn("run OCR first", summary["failed"][0]["error"])

    def test_render_pdf_pages_to_images_moves_pdf_and_names_pages_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "demo-project"
            imported_dir = project / "imported"
            imported_dir.mkdir(parents=True)
            pdf_path = imported_dir / "sample.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")

            class FakePixMap:
                def save(self, path, **kwargs):
                    Path(path).write_bytes(b"jpg")

            class FakePage:
                def __init__(self):
                    self.calls = 0

                def get_pixmap(self, matrix=None):
                    self.calls += 1
                    return FakePixMap()

            class FakeDoc:
                def __init__(self):
                    self.pages = [FakePage(), FakePage()]

                def __len__(self):
                    return len(self.pages)

                def __getitem__(self, index):
                    return self.pages[index]

                def close(self):
                    return None

            fake_fitz = mock.Mock()
            fake_fitz.open.return_value = FakeDoc()

            with mock.patch("workflow_runner.tasks.ocr_task.pymupdf", fake_fitz, create=True):
                images = render_pdf_pages_to_images(project, pdf_path)

            self.assertEqual([path.name for path in images], ["sample_0001.jpg", "sample_0002.jpg"])
            self.assertTrue((project / "imported" / "sample_0001.jpg").exists())
            self.assertTrue((project / "imported" / "sample_0002.jpg").exists())
            self.assertTrue((project / "processed_pdf" / "sample.pdf").exists())
            self.assertFalse(pdf_path.exists())

    def test_interpret_emits_progress_logs_for_ui_stream(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "demo-project"
            (project / "metadata").mkdir(parents=True)
            (project / "imported").mkdir(parents=True)
            (project / "GLOSSARIO.md").write_text("# Glossary\n", encoding="utf-8")
            metadata_path = project / "metadata" / "sample_0001.json"
            metadata_path.write_text(
                json.dumps(
                    {
                        "image": "sample_0001.jpg",
                        "document_type": "test",
                        "document_date": "2024",
                        "location": "",
                        "full_transcript": "text",
                        "entities": {"names": [], "dates": [], "places": [], "values": []},
                        "properties": [],
                        "persons": [],
                        "relations": [],
                        "ocr_metadata": {"status": "done", "notes": "ok"},
                    }
                ),
                encoding="utf-8",
            )

            def fake_request(messages, model, image=None):
                return {
                    "image": "sample_0001.jpg",
                    "document_type": "test",
                    "document_date": "2024",
                    "location": "",
                    "full_transcript": "text",
                    "entities": {"names": [], "dates": [], "places": [], "values": []},
                    "properties": [],
                    "persons": [],
                    "relations": [],
                    "ocr_metadata": {"status": "done", "notes": "ok"},
                }

            stdout = StringIO()
            with mock.patch("workflow_runner.tasks.interpret_task._request_json", side_effect=fake_request):
                with mock.patch("sys.stdout", stdout):
                    summary = run_interpret(project, "model-x")

        self.assertEqual(summary["processed"], 1)
        self.assertIn("Interpreting sample_0001.json", stdout.getvalue())
        self.assertIn("Interpreted sample_0001.json", stdout.getvalue())

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
