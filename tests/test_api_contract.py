import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import api.server as server
from api.server import app


class ApiContractTests(unittest.TestCase):
    def test_openapi_document_is_served(self):
        with app.test_client() as client:
            response = client.get("/api/openapi.json")

        self.assertEqual(response.status_code, 200)
        document = response.get_json()
        self.assertEqual(document["openapi"], "3.0.3")
        self.assertIn("/api/projects/{name}/process", document["paths"])
        self.assertNotIn("model", document["paths"]["/api/projects/{name}/process"]["post"]["requestBody"])

    def test_process_stream_returns_sse_with_live_auth_code(self):
        class FakeStdout:
            def __init__(self, lines):
                self._lines = iter(lines)

            def readline(self):
                try:
                    return next(self._lines)
                except StopIteration:
                    return ""

            def close(self):
                pass

        with mock.patch("api.server.subprocess.Popen") as popen, app.test_client() as client:
            process = mock.Mock()
            process.stdout = FakeStdout(["Please visit https://github.com/login/device and enter code ABCD-EFGH\n", ""])
            process.wait.return_value = 0
            popen.return_value = process

            response = client.post("/api/projects/demo/process", json={"mode": "ocr", "stream": True})

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.content_type)
        body = response.get_data(as_text=True)
        self.assertIn("ABCD-EFGH", body)

    def test_process_stream_has_generic_runner_output(self):
        class FakeStdout:
            def __init__(self, lines):
                self._lines = iter(lines)

            def readline(self):
                try:
                    return next(self._lines)
                except StopIteration:
                    return ""

            def close(self):
                pass

        with mock.patch("api.server.subprocess.Popen") as popen, app.test_client() as client:
            process = mock.Mock()
            process.stdout = FakeStdout(["worker output line\n", ""])
            process.wait.return_value = 0
            popen.return_value = process

            response = client.post("/api/projects/demo/process", json={"mode": "ocr", "stream": True})

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.content_type)
        self.assertIn("worker output line", response.get_data(as_text=True))

    def test_process_stream_preserves_runner_error_hint_for_copilot_auth(self):
        class FakeStdout:
            def __init__(self, lines):
                self._lines = iter(lines)

            def readline(self):
                try:
                    return next(self._lines)
                except StopIteration:
                    return ""

            def close(self):
                pass

        with mock.patch("api.server.subprocess.Popen") as popen, app.test_client() as client:
            process = mock.Mock()
            process.stdout = FakeStdout([
                '{"ok": false, "error": "GitHub Copilot requires device login.", "hint": "Open https://github.com/login/device and enter code ABCD-EFGH", "operation": "ocr"}\n',
                "",
            ])
            process.wait.return_value = 1
            popen.return_value = process

            response = client.post("/api/projects/demo/process", json={"mode": "ocr", "stream": True})

        self.assertEqual(response.status_code, 200)
        content = response.get_data(as_text=True)
        self.assertIn("GitHub Copilot requires device login", content)
        self.assertIn("ABCD-EFGH", content)
        self.assertIn('"status": "error"', content)

    def test_checked_in_openapi_document_is_valid_json(self):
        with open("api/openapi.json", encoding="utf-8") as handle:
            document = json.load(handle)

        self.assertIn("paths", document)
        self.assertIn("components", document)

    def test_project_details_reports_pending_map_and_old_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects_dir = root / "projects"
            project_dir = projects_dir / "demo"
            imported_dir = project_dir / "imported"
            imported_dir.mkdir(parents=True)
            (project_dir / "metadata").mkdir(parents=True)
            (imported_dir / "a.jpg").write_text("a", encoding="utf-8")
            (imported_dir / "b.png").write_text("b", encoding="utf-8")
            (project_dir / "docs_logical_map.json").write_text(
                json.dumps({"schema_version": "2.0", "logical_documents": []}),
                encoding="utf-8",
            )
            (project_dir / "docs_logical.json").write_text(
                json.dumps({
                    "schema_version": "2.0",
                    "total_logical_documents": 1,
                    "total_images": 1,
                    "persons": [],
                    "relations": [],
                    "documents": [],
                }),
                encoding="utf-8",
            )

            with mock.patch.object(server, "PROJECTS_DIR", projects_dir):
                with app.test_client() as client:
                    response = client.get("/api/projects/demo/details")

        self.assertEqual(response.status_code, 200)
        details = response.get_json()
        self.assertEqual(details["images"], 2)
        self.assertEqual(details["mapDocuments"], 0)
        self.assertEqual(details["mapImages"], 0)
        self.assertEqual(details["docsTotalImages"], 1)

    def test_project_details_reports_pending_docs_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects_dir = root / "projects"
            project_dir = projects_dir / "demo"
            imported_dir = project_dir / "imported"
            imported_dir.mkdir(parents=True)
            (project_dir / "metadata").mkdir(parents=True)
            (imported_dir / "a.jpg").write_text("a", encoding="utf-8")
            (project_dir / "docs_logical_map.json").write_text(
                json.dumps({"schema_version": "2.0", "logical_documents": [{"id": "dl-1", "title": "doc", "type": "sale", "images": ["a.jpg"]}]}),
                encoding="utf-8",
            )

            with mock.patch.object(server, "PROJECTS_DIR", projects_dir):
                with app.test_client() as client:
                    response = client.get("/api/projects/demo/details")

        self.assertEqual(response.status_code, 200)
        details = response.get_json()
        self.assertEqual(details["images"], 1)
        self.assertEqual(details["mapDocuments"], 1)
        self.assertEqual(details["mapImages"], 1)
        self.assertEqual(details["docsTotalImages"], 0)

    def test_process_route_forwards_only_new_flag_to_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects_dir = root / "projects"
            project_dir = projects_dir / "demo"
            (project_dir / "imported").mkdir(parents=True)
            (project_dir / "metadata").mkdir(parents=True)
            (project_dir / "GLOSSARIO.md").write_text("# Glossary\n", encoding="utf-8")
            (project_dir / "docs_logical_map.json").write_text(json.dumps({"schema_version": "2.0", "logical_documents": []}), encoding="utf-8")
            (project_dir / "docs_logical.json").write_text(json.dumps({"schema_version": "2.0", "documents": [], "persons": [], "relations": [], "properties": []}), encoding="utf-8")

            with mock.patch.object(server, "PROJECTS_DIR", projects_dir), \
                 mock.patch("api.server.subprocess.run") as run_mock:
                run_mock.return_value.returncode = 0
                run_mock.return_value.stdout = '{"operation": "ocr"}\n'
                run_mock.return_value.stderr = ''

                with app.test_client() as client:
                    response = client.post("/api/projects/demo/process", json={"mode": "ocr", "only_new": True})

        self.assertEqual(response.status_code, 200)
        command = run_mock.call_args[0][0]
        self.assertIn("--only-new", command)


if __name__ == "__main__":
    unittest.main()