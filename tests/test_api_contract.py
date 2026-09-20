import json
import unittest

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

    def test_checked_in_openapi_document_is_valid_json(self):
        with open("api/openapi.json", encoding="utf-8") as handle:
            document = json.load(handle)

        self.assertIn("paths", document)
        self.assertIn("components", document)


if __name__ == "__main__":
    unittest.main()