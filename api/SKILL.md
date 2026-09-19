# 🤖 SKILL.md — API Development with GenAI

**Component:** NotaryMindAi REST API Server  
**Technology:** Python 3, Flask, CORS  
**GenAI Model:** Claude (any version, Claude 3.5 Sonnet recommended)  
**Purpose:** Develop, enhance, and maintain `api/server.py` using GenAI assistance  

---

## 📋 Quick Prompts for API Development

### 1. Add a New Endpoint

**Prompt Template:**
```
I need to add a new endpoint to NotaryMindAi API. Here's what I need:

ENDPOINT SPEC:
- Method: GET or POST
- Path: /api/...
- Purpose: [describe what it does]
- Input: [describe request format]
- Output: [describe response format]

CONSTRAINTS:
- Read-only (no writes)? YES/NO
- Affects projects/? YES/NO
- Authentication needed? NO (local dev)

Current server structure:
[paste relevant code from api/server.py]

Please write the endpoint handler following the existing patterns in my server.py.
Ensure it includes:
- Input validation
- Error handling with proper HTTP status codes
- CORS-compatible response format
```

**Example:**
```
I need to add a GET endpoint that lists all persons in a project.

ENDPOINT SPEC:
- Method: GET
- Path: /api/projects/{name}/persons
- Purpose: List all persons (genealogical data) in a project
- Input: {project name in URL}
- Output: {persons: [{id, name, gender, birth, roles}]}

CONSTRAINTS:
- Read-only: YES
- Affects projects: NO (read-only)
- Authentication: NO

Current code:
[paste `agent_query` function as reference]

Please write the endpoint using the same patterns.
```

### 2. Improve Query Algorithm

**Prompt:**
```
Help me improve the genealogical search in /api/agent/query.

CURRENT ALGORITHM:
[paste `agent_query` function]

IMPROVEMENTS NEEDED:
- Better scoring for relation types (filiation should rank higher)
- Handle name variants (e.g., "João" vs "João Maria")
- Support date ranges ("pessoas em 1872")
- Exclude exact matches from multiple scoring

CONSTRAINTS:
- Normalize text (remove accents, case-insensitive)
- Portuguese language awareness
- Performance: keep < 100ms for projects with 100+ persons

Please enhance the scoring logic while maintaining backward compatibility.
```

### 3. Add File Upload Validation

**Prompt:**
```
I need to improve file upload validation for /api/projects/{name}/upload.

CURRENT CODE:
[paste `uploadFiles` or relevant upload handler]

REQUIREMENTS:
- Only accept: .jpg, .jpeg, .png, .gif, .webp, .pdf
- Maximum file size: 50MB per file, 500MB per batch
- Detect and reject corrupted images
- Organize by date uploaded or keep flat in imported/

CONSTRAINTS:
- No external libraries (use PIL/Pillow if already in requirements)
- Preserve original filenames
- Return detailed response: {saved, skipped, errors, total}

Please add validation and improve the handler.
```

### 4. Error Handling & Logging

**Prompt:**
```
Add comprehensive error handling to the API.

CURRENT PATTERNS:
[paste 2-3 existing error returns from server.py]

NEEDED:
- Structured error responses: {error, code, status}
- Logging for debugging (console + optional file)
- Distinguish: client errors (400) vs server errors (500)
- Validation errors should explain what's wrong

CONSTRAINTS:
- Keep it simple (no external logging libraries for v2)
- Log to console (stdout)
- Don't expose sensitive paths in error messages

Please add error handling across all endpoints.
```

### 5. Docker Support

**Prompt:**
```
Help me create a Dockerfile for the API.

API DETAILS:
- Python 3.10+
- Flask app in api/server.py
- Serves UI from ../ui/
- Data from ../projects/
- Port: 8787
- Entry: python3 server.py

REQUIREMENTS:
- Lightweight image (alpine or slim)
- Multi-stage build (optional)
- Support PORT environment variable
- Mount volumes for projects/ data
- Health check endpoint

Please generate:
1. Dockerfile for api/
2. Example docker-compose.yml (full stack)
3. .dockerignore file
```

---

## 🧬 Code Patterns to Use

### Pattern 1: New Endpoint Handler

```python
@app.route("/api/projects/<name>/<action>", methods=["GET", "POST"])
def api_projects_action(name, action):
    """Brief description of what this endpoint does."""
    # 1. Validate input
    name = safe_name(name)
    if not name:
        return json({"error": "Project name invalid"}, 400)
    
    # 2. Check preconditions
    if action == "data":
        data = load_project_data(name)
        if not data:
            return json({"error": "No data"}, 404)
        return json(data)
    
    # 3. Handle action
    if action == "new_action":
        try:
            # Do something
            result = {}
            return json({"ok": True, "result": result})
        except Exception as e:
            return json({"error": str(e)}, 500)
    
    # 4. Unknown action
    return json({"error": "Unknown action"}, 400)
```

### Pattern 2: Query/Search Function

```python
def search_genealogy(project: str, query_terms: list) -> list:
    """Search with scoring and normalization."""
    data = load_project_data(project)
    if not data:
        return []
    
    results = []
    
    # Search persons
    for person in data.get("persons", []):
        score = 0
        for term in query_terms:
            # Check names, roles, dates, etc.
            if normalize(term) in normalize(person.get("name", "")):
                score += 2
            if normalize(term) in " ".join(person.get("roles", [])):
                score += 1
        if score > 0:
            results.append({"kind": "person", "data": person, "_score": score})
    
    # Sort by score
    results.sort(key=lambda r: r["_score"], reverse=True)
    return results[:25]
```

### Pattern 3: Safe Path Handling

```python
def safe_join(base: Path, rel: str) -> Path | None:
    """Resolve relative path within base (prevent traversal)."""
    try:
        target = (base / ("." + (rel if rel.startswith("/") else "/" + rel))).resolve()
        base_resolved = base.resolve()
        if target == base_resolved or str(target).startswith(str(base_resolved) + "/"):
            return target
    except Exception:
        pass
    return None
```

### Pattern 4: CORS + JSON Response

```python
def json(body: unknown, status=200) -> Response:
    return Response(
        json.dumps(body),
        status=status,
        headers={
            "content-type": "application/json",
            "access-control-allow-origin": "*",
            "access-control-allow-methods": "GET,POST,OPTIONS",
            "access-control-allow-headers": "content-type",
        }
    )
```

---

## 🧪 Testing with GenAI

### Automatic Test Suite

The project includes `test_api.sh` — an automated test script that verifies:
- Server startup
- API endpoints (list, create, upload, query)
- Error handling
- CORS headers
- UI serving

**Important:** When you add new endpoints using GenAI, you MUST update `test_api.sh` to test them.

### Test-Driven Development with GenAI

**Prompt Template:**
```
I'm using GenAI to develop new API features. I've generated a new endpoint:

[paste new endpoint code]

Please generate:
1. Test case(s) for this endpoint
2. Integration test to add to test_api.sh
3. Error cases to test
4. Example curl commands

Format output as bash tests compatible with test_api.sh.
```

### Running Tests

```bash
# From api/ directory
bash test_api.sh [port]

# Default (port 8787)
bash test_api.sh

# Custom port
bash test_api.sh 9000

# With capture of output
bash test_api.sh 8787 > test_results.log 2>&1
```

### Evolving Tests with Features

Whenever you add a new endpoint:

1. **Use GenAI to generate endpoint code** (from api/SKILL.md)
2. **Ask GenAI to generate test cases** (use prompt above)
3. **Add tests to `api/test_api.sh`** with descriptive names
4. **Run full test suite:** `bash test_api.sh`
5. **Verify all tests pass** before committing

Example new test in test_api.sh:
```bash
echo "[N] Your new feature test:"
curl -s http://localhost:8787/api/your-new-endpoint \
  -H 'Content-Type: application/json' \
  -d '{...}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('✓ Test passed' if d.get('ok') else '✗ Failed')"
```

### Test Coverage Goals

- ✅ Happy path (request succeeds)
- ✅ Error cases (invalid input, missing data)
- ✅ HTTP status codes (200, 400, 404, 500)
- ✅ CORS headers present
- ✅ Response format matches schema
- ✅ Read-only guarantee (agent endpoint)

---

### Prompt: Generate Integration Tests

```
Generate pytest tests for the API endpoints.

ENDPOINTS TO TEST:
- GET /api/projects
- POST /api/projects
- DELETE /api/projects/{name}
- GET /api/projects/{name}/details
- POST /api/projects/{name}/upload
- GET and PUT /api/projects/{name}/glossary
- POST /api/projects/{name}/process (mock subprocess and GenAI runner)
- POST /api/projects/{name}/tools (audit inference, validate map, validate variants)
- POST /api/agent/query

REQUIREMENTS:
- Mock filesystem (tmpdir)
- Verify new projects personalize `skills/transcript/GLOSSARY-TEMPLATE.md` into an operational,
  parser-compatible `GLOSSARIO.md`; missing templates must not leave partial projects
- Verify recursive deletion cannot escape `PROJECTS_DIR`
- Test happy path + error cases
- Verify CORS headers present
- Test with invalid inputs (SQL injection, path traversal)

API SERVER CODE:
[paste relevant parts]

Please generate pytest tests in tests/test_api.py
```

### Prompt: Generate Test Data

```
Generate realistic test data for genealogical projects.

SCHEMA REFERENCE:
[paste from SCHEMA.md]

NEEDED:
- 5-10 persons with Portuguese names
- 15-20 family relations (filiation, kinship)
- 2-3 historical property documents (1800s)
- Valid JSON matching schema

Output format:
{
  "persons": [...],
  "relations": [...],
  "documents": [...]
}
```

---

## 📊 Data Structures for GenAI Context

### Project Data Schema

```json
{
  "schema_version": "2.0",
  "name": "String",
  "description": "String",
  "timestamp": "ISO 8601",
  "persons": [
    {
      "name": "String",
      "gender": "M|F|U",
      "gender_source": "explicit|inferred|context",
      "birth": "YYYY-MM-DD",
      "death": "YYYY-MM-DD",
      "roles": ["String"],
      "variants": ["String"]
    }
  ],
  "relations": [
    {
      "from": "String (person name)",
      "to": "String (person name)",
      "attribute": "filiation|kinship|other",
      "relation": "Portuguese label",
      "source": "explicit|inferred",
      "inference_confidence": "high|medium|low"
    }
  ],
  "documents": [
    {
      "id": "String",
      "title": "String",
      "document_type": "Deed|Will|Certificate|...",
      "document_date": ["YYYY-MM-DD"],
      "entities": {"names": ["String"]},
      "transaction": {
        "buyer": "String",
        "seller": "String",
        "value": "String"
      },
      "properties": []
    }
  ]
}
```

### API Response Contracts

**Projects List:**
```json
{
  "projects": [
    {
      "name": "cotimos",
      "hasData": true,
      "images": 59,
      "docs": 23
    }
  ]
}
```

**Agent Query:**
```json
{
  "answer": "Encontrei 3 pessoa(s)...",
  "hits": [
    {
      "kind": "person|relation|document",
      "id": "unique-id",
      "label": "Display name",
      "detail": "Additional info",
      "link": "#person=P%3Aname"
    }
  ],
  "readonly": true,
  "project": "cotimos"
}
```

### Project File Editor Endpoint

`GET|PUT /api/projects/<name>/file/<file_name>` — reads or saves one whitelisted project
file for the Build Metadata generic text editor in the UI. Whitelist (`file_name` → JSON validated?):

| File | JSON validated on save? |
|------|--------------------------|
| `GLOSSARIO.md` | No (Markdown) |
| `docs_logical_map.json` | Yes |
| `docs_logical.json` | Yes |
| `gender_rules.json` | Yes |

Any other `file_name` returns `400 {"error": "Project file is not editable"}`.

**GET response:**
```json
{"file": "gender_rules.json", "content": "{...raw file text, empty string if file doesn't exist yet...}"}
```

**PUT request/response:**
```json
// request body
{"content": "raw file text"}
// response
{"ok": true, "file": "gender_rules.json"}
```
JSON-whitelisted files are parsed with `json.loads()` before saving; invalid JSON returns
`400 {"error": "Invalid JSON: <message>"}` and the file is left unchanged.

---

## 🎯 Common Development Tasks

### Task 1: Add Portuguese Language Support

**Prompt:**
```
Enhance the API to better handle Portuguese genealogical data.

REQUIREMENTS:
- Normalize diacritics (ã→a, ç→c, etc.)
- Recognize Portuguese relation types: "filho", "filha", "pai", "mãe", "esposo", "esposa"
- Handle date formats: "1º de Janeiro de 1872" → "1872-01-01"
- Support Portuguese role keywords

CURRENT NORMALIZATION:
[paste normalize() function]

Please enhance it for Portuguese while maintaining performance.
```

### Task 2: Optimize Query Performance

**Prompt:**
```
Profile and optimize the agent_query function for large datasets.

CURRENT IMPLEMENTATION:
[paste agent_query]

PERFORMANCE TARGETS:
- < 100ms for 1000 persons + relations
- < 500ms for full index rebuild
- Memory: < 100MB for large project

PROFILING DATA:
[if available: paste timings]

Please identify bottlenecks and suggest optimizations:
- Indexing strategy
- Caching opportunities
- Algorithm improvements
```

### Task 3: Add Batch Operations

**Prompt:**
```
Add support for bulk project operations.

USE CASES:
- Batch import from folder
- Export all projects to backup
- Merge two projects
- Duplicate project with new name

CONSTRAINTS:
- Maintain data integrity
- Query-only agent (no write access for agent)
- Atomic operations (all-or-nothing)

Please design and implement batch endpoints.
```

---

## 🔗 Integration with Other Skills

### When to Use Each Skill

| Need | Skill | File |
|------|-------|------|
| **Transcribe images with GenAI** | `skills/transcript/SKILL.md` | `build_docs_logical.py` |
| **Enhance UI with GenAI** | `ui/SKILL.md` | `main.html` |
| **Develop/improve API** | `api/SKILL.md` | `server.py` (this file) |
| **Understand data model** | Root `SCHEMA.md` | Data contracts |

### GenAI Workflow Example

```
1. User uploads historical images to project
   → API: POST /api/projects/{name}/upload

2. Run transcript skill with GenAI (Claude)
   → Skill: skills/transcript/SKILL.md
   → Tool: python3 build_docs_logical.py {project}
   → Output: projects/{name}/docs_logical.json

3. Query genealogy via UI
   → API: POST /api/agent/query
   → Returns: Links to persons, documents, relations

4. User refines data (e.g., correct gender inference)
   → Edit projects/{name}/docs_logical.json

5. Rebuild with updated rules
   → Skill: skills/transcript/SKILL.md
   → Loop to step 3
```

---

## 📚 Useful GenAI Prompts Collection

### Refactor Code

```
Refactor the following Flask handler to be more Pythonic and maintainable:
[paste function]

Guidelines:
- Use pathlib instead of os.path
- Type hints where helpful
- Docstrings for clarity
- Error handling with context managers
- No breaking changes to API contract
```

### Security Review

```
Review the following code for security issues:
[paste function]

Check for:
- Path traversal attacks
- SQL injection (if applicable)
- XSS vulnerabilities
- CORS misconfiguration
- Rate limiting needs

Provide:
1. Issues found
2. Risk severity
3. Recommended fixes
```

### Documentation

```
Generate OpenAPI/Swagger documentation for these endpoints:
[paste routes]

Output format:
```yaml
openapi: 3.0.0
paths:
  /api/projects:
    get:
      summary: ...
```

### API Design

```
Design a new endpoint for [use case].

Context:
- Existing schema: [paste SCHEMA.md excerpt]
- Current patterns: [paste 2-3 similar endpoints]
- User need: [describe what users want to do]

Please suggest:
1. Endpoint path and method
2. Request format
3. Response format
4. Error cases
5. Implementation outline
```

---

## 🚀 Getting Started

### For API Development:

1. **Understand the codebase:**
   - Read `api/README.md`
   - Review `api/server.py` structure
   - Check `SCHEMA.md` for data contracts

2. **Propose changes to Claude:**
   ```
   I want to [add/fix/improve] the API.
   
   Current code:
   [paste relevant parts]
   
   Desired behavior:
   [describe what should happen]
   
   Please [generate/review/refactor] the code.
   ```

3. **Test locally:**
   ```bash
   python3 api/server.py
   # http://localhost:8787/api/...
   ```

4. **Iterate:**
   - Get Claude's suggestions
   - Apply changes
   - Test
   - Commit

### Tips for Effective GenAI Sessions:

- **Be specific:** Paste relevant code, not entire files
- **Show context:** Mention constraints, performance needs, compatibility
- **Ask for patterns:** Request code following existing style
- **Validate output:** Always test generated code
- **Request documentation:** Ask for docstrings and examples
- **Iterate:** Build features incrementally with GenAI

---

## 📖 Related Documentation

- [`../README.md`](../README.md) — Project overview and current architecture
- [`../skills/transcript/SCHEMA.md`](../skills/transcript/SCHEMA.md) — Data contract reference
- [`../skills/transcript/SKILL.md`](../skills/transcript/SKILL.md) — OCR/transcription workflows
- [`../ui/SKILL.md`](../ui/SKILL.md) — UI behavior and development

---

**Version:** 2.0  
**Last Updated:** September 16, 2026  
**Maintained By:** NotaryMindAi Team
