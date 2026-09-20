import json
import unittest
from unittest import mock

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


if __name__ == "__main__":
    unittest.main()