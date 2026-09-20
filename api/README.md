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
- `GENAI_PROVIDER` — Provider selection (`copilot`, `openai`, `anthropic`, `azure`, `vertex_ai`, `bedrock`, `ollama`, `lmstudio`)
- `GITHUB_COPILOT_API_BASE` — Copilot base URL; default `https://api.githubcopilot.com`. This does not use `OPENAI_API_KEY`.
- `OPENAI_API_KEY` / `OPENAI_API_BASE` — OpenAI-compatible provider settings
- `ANTHROPIC_API_KEY` / `ANTHROPIC_API_BASE` — Anthropic provider settings
- `NOTARYMIND_<OPERATION>_MODEL` or `NOTARYMIND_GENAI_MODEL` — Optional model overrides for the built-in workflow runner used by processing modes `ocr`, `reinterpret`, and `map`. Modes `build` and `validate-docs` run locally without model selection.

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
- `POST /api/projects/{name}/process` — Run named operation `ocr`, `reinterpret`, `build`, `map`, or `validate-docs`; `ocr`, `reinterpret`, and `map` invoke the built-in `workflow_runner/runner.py` script directly, while `build` and `validate-docs` run locally. Failures return the captured runner stdout/stderr in the JSON response so the UI can display the underlying error.
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

This API is part of NotaryMindAi monorepo:
- `api/` — This service (Python backend)
- `ui/` — Frontend (HTML/JS)
- `projects/` — Project data
- `skills/` — Processing tools and workflow documentation

See the parent `README.md` for the current architecture and endpoint overview.
