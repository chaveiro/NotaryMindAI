# NotaryMindAi — API Server

Python Flask REST API for multi-project genealogical data management.

## 🤖 GenAI Development

To develop or enhance this API using GenAI (Claude, etc.):

**See: [SKILL.md](SKILL.md)**

Contains:
- Ready-to-use prompts for adding endpoints
- Code patterns (Flask, Python, CORS)
- Testing strategies
- Data schema reference
- Common development tasks

## Installation

```bash
pip install -r requirements.txt
# or
sudo apt-get install python3-flask python3-flask-cors
```

## Running

```bash
python3 server.py
# Server: http://localhost:8787
```

## Environment

- `PORT` — Server port (default 8787)
  ```bash
  PORT=9000 python3 server.py
  ```

The API remains provider-neutral. It invokes the generic worker entry point and streams stdout/stderr back to the UI with SSE. Provider-specific logic stays inside `workflow_runner/runner.py`.

When the UI is served separately, pass the API origin explicitly, for example:
`http://localhost:8000/ui/main.html?project=cotimos&api=http://localhost:8790`.
The UI rejects HTML responses from missing `/api` routes and tries its local development
fallbacks (`8787`, then `8790`) instead of attempting to parse HTML as JSON.

## API Endpoints

See parent README.md for full API documentation.

### Key Endpoints

- `GET /api/projects` — List all projects
- `POST /api/projects` — Create a project with a schema-valid `logical_documents` map and copy/personalize `skills/transcript/GLOSSARY-TEMPLATE.md` as its operational `GLOSSARIO.md`
- `DELETE /api/projects/{name}` — Delete a project folder and all of its contents
- `GET /api/projects/{name}/details` — Get imported/metadata processing status
- `POST /api/projects/{name}/upload` — Upload files
- `GET|PUT /api/projects/{name}/glossary` — Read or save `GLOSSARIO.md`
- `GET|PUT /api/projects/{name}/file/{file_name}` — Edit `GLOSSARIO.md`, `docs_logical_map.json`, `docs_logical.json`, or `gender_rules.json`
- `POST /api/projects/{name}/process` — Run named operation `ocr`, `interpret`, `build`, `map`, or `validate-docs`; `ocr`, `interpret`, and `map` invoke the built-in `workflow_runner/runner.py` script directly, while `build` and `validate-docs` run locally. When `stream: true` is used, the server emits SSE log/result events from the worker and the UI can show the live prompt and final status without rewriting the provider logic in the API layer.
- `POST /api/projects/{name}/tools` — Run `audit-inference`, `validate-map`, or `validate-variants` and return captured output/exit code
- `POST /api/agent/query` — Query genealogical data (read-only)

## Development

The server serves:
- UI: `../ui/` (static files)
- Data: `../projects/` (project directories)
- Tools: `../skills/` (build, validation, and transcript workflows)

## Testing

### Run Tests

```bash
# From api/ directory
bash test_api.sh [port]

# Example (default port 8787)
bash test_api.sh

# Custom port
bash test_api.sh 9000
```

The current shell smoke suite covers server startup, project listing/creation, project
data and raw-file reads, read-only agent queries, and static UI serving. Test destructive
or write-heavy endpoints (upload, deletion, glossary writes, and processing) with a
temporary `PROJECTS_DIR` and mocked subprocess/GenAI runners.

**Note:** When adding new endpoints with GenAI (see SKILL.md), remember to add corresponding tests to `test_api.sh`.

## Architecture

This API is part of a single monorepo:
- `api/` — This service (Python backend)
- `ui/` — Frontend (HTML/JS)
- `projects/` — Project data
- `skills/` — Processing tools and workflow documentation

See the parent `README.md` for the overall project structure and workflow overview.
