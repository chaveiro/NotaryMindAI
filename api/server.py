#!/usr/bin/env python3
"""
NotaryMindAi — Standalone API server (agnostic: runs with or without piclaw)

Provides a simple HTTP API for the web portal:
  - GET  /api/projects                     list projects
  - POST /api/projects                     create a new project (mkdir in projects/)
  - POST /api/projects/:name/upload        upload raw documents (multipart, multi-file)
  - GET  /api/projects/:name/data          docs_logical.json for a project
  - GET  /api/projects/:name/raw?path=...   read a file inside the project (images/metadata)
  - POST /api/agent/query                   QUERY-ONLY agent (no writes, returns links)

Static:
  - GET / , /ui/*                          serves the UI (main.html, schema.json)
  - GET /projects/:name/imported/:img      serves project images

Query-only guarantee: the agent endpoint never writes files or mutates metadata.
It only reads docs_logical.json and returns matches as links to app elements.

Run:  python3 api/server.py            (defaults to port 8787)
      PORT=9000 python3 api/server.py
"""

import os
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from urllib.parse import quote, unquote
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# API is in api/ subdirectory, so parent points to NotaryMindAi/
ROOT = Path(__file__).parent.parent.resolve()
PROJECTS_DIR = ROOT / "projects"
UI_DIR = ROOT / "ui"
GLOSSARY_TEMPLATE_PATH = ROOT / "skills/transcript/GLOSSARY-TEMPLATE.md"
GENDER_RULES_TEMPLATE_PATH = ROOT / "skills/transcript/GENDER-RULES-TEMPLATE.json"
PORT = int(os.environ.get("PORT", 8787))
GENAI_MODEL = "github-copilot/claude-opus-4.8"
SUPPORTED_IMPORT_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf")

# ========== Helpers ==========

def safe_name(name: str) -> str | None:
    """Validate project name (alphanumeric, dash, underscore only)."""
    if not name:
        return None
    n = name.strip()
    if n in (".", ".."):
        return None
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$", n):
        return None
    return n


def safe_join(base: Path, rel: str) -> Path | None:
    """Safely resolve a relative path within a base directory (prevent traversal)."""
    try:
        target = (base / ("." + (rel if rel.startswith("/") else "/" + rel))).resolve()
        base_resolved = base.resolve()
        if target == base_resolved or str(target).startswith(str(base_resolved) + "/"):
            return target
    except Exception:
        pass
    return None


def normalize(s: str) -> str:
    """Normalize text for search: remove accents, lowercase, trim whitespace."""
    s = (s or "").strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s


def project_details(entry: Path) -> dict:
    """Return processing status for one project directory."""
    data_path = entry / "docs_logical.json"
    imported_dir = entry / "imported"
    metadata_dir = entry / "metadata"
    imported_files = sorted(
        [f for f in imported_dir.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_IMPORT_SUFFIXES]
    ) if imported_dir.exists() else []
    metadata_files = {f.stem: f for f in metadata_dir.glob("*.json")} if metadata_dir.exists() else {}
    pending = [f.name for f in imported_files if f.stem not in metadata_files]
    stale = [
        f.name for f in imported_files
        if f.stem in metadata_files and metadata_files[f.stem].stat().st_mtime < f.stat().st_mtime
    ]

    docs = 0
    persons = 0
    relations = 0
    properties = 0
    if data_path.exists():
        try:
            with open(data_path) as file_handle:
                data = json.load(file_handle)
            docs = data.get("total_logical_documents", len(data.get("documents", [])))
            persons = len(data.get("persons", []))
            relations = len(data.get("relations", []))
            properties = len(data.get("properties", []))
            if not properties:
                properties = sum(
                    len(document.get("properties", []))
                    for document in data.get("documents", [])
                )
        except Exception:
            pass

    return {
        "name": entry.name,
        "hasData": data_path.exists(),
        "images": len(imported_files),
        "docs": docs,
        "persons": persons,
        "relations": relations,
        "properties": properties,
        "metadata": len(metadata_files),
        "pendingMetadata": len(pending),
        "staleMetadata": len(stale),
        "metadataUpdated": not pending and not stale,
        "pendingFiles": pending,
        "staleFiles": stale,
        "hasGlossary": (entry / "GLOSSARIO.md").exists(),
        "hasMap": (entry / "docs_logical_map.json").exists(),
    }


def list_projects() -> list:
    """List all projects with processing status."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return [project_details(entry) for entry in sorted(PROJECTS_DIR.iterdir()) if entry.is_dir()]


def glossary_template(project_name: str, label: str, created_at: str) -> str:
    """Load and personalize the glossary shared by build and OCR workflows."""
    template = GLOSSARY_TEMPLATE_PATH.read_text(encoding="utf-8")
    return (template
        .replace("{{PROJECT_NAME}}", project_name)
        .replace("{{PROJECT_LABEL}}", label)
        .replace("{{CREATED_AT}}", created_at))


def create_project(name: str, display_name: str | None = None) -> dict:
    """Scaffold a new project with standard structure."""
    dir_path = PROJECTS_DIR / name
    if dir_path.exists():
        return {"ok": False, "error": "Project already exists"}
    
    try:
        label = (display_name or name).strip() if display_name else name
        created_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        glossary_content = glossary_template(name, label, created_at)

        (dir_path / "imported").mkdir(parents=True, exist_ok=True)
        (dir_path / "metadata").mkdir(parents=True, exist_ok=True)

        # Minimal docs_logical.json
        empty_data = {
            "schema_version": "2.0",
            "name": label,
            "description": f"Archive {label}",
            "timestamp": json.dumps({'__str__': 'ISO_NOW'}).replace('{\"__str__\": \"ISO_NOW\"}', 'ISO_NOW'),
            "total_logical_documents": 0,
            "total_images": 0,
            "persons": [],
            "relations": [],
            "documents": [],
        }
        empty_data["timestamp"] = created_at
        
        with open(dir_path / "docs_logical.json", "w") as f:
            json.dump(empty_data, f, indent=2)
        
        with open(dir_path / "docs_logical_map.json", "w") as f:
            json.dump({
                "schema_version": "2.0",
                "name": label,
                "description": f"Archive {label}",
                "logical_documents": [],
            }, f, indent=2)
        
        with open(dir_path / "gender_rules.json", "w") as f:
            gender_template = json.loads(GENDER_RULES_TEMPLATE_PATH.read_text(encoding="utf-8"))
            json.dump(gender_template, f, indent=2)
        
        with open(dir_path / "GLOSSARIO.md", "w") as f:
            f.write(glossary_content)
        
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def load_project_data(name: str) -> dict | None:
    """Load docs_logical.json for a project."""
    data_path = PROJECTS_DIR / name / "docs_logical.json"
    if not data_path.exists():
        return None
    try:
        with open(data_path) as f:
            return json.load(f)
    except Exception:
        return None


def agent_query(project: str, question: str) -> dict:
    """Query-only agent: search docs_logical.json and return links."""
    data = load_project_data(project)
    if not data:
        return {
            "answer": f'Project "{project}" has no loaded data.',
            "hits": [],
        }
    
    q = normalize(question)
    terms = [t for t in q.split() if len(t) > 2]
    
    persons = data.get("persons", [])
    relations = data.get("relations", [])
    documents = data.get("documents", [])
    
    hits = []
    
    def score(text: str) -> int:
        t = normalize(text)
        s = 0
        for term in terms:
            if term in t:
                s += 1
        return s
    
    # Search persons
    for p in persons:
        hay = " ".join([
            p.get("name", ""),
            *[v if isinstance(v, str) else v.get("name", "") for v in p.get("variants", [])],
            p.get("role", ""),
            *p.get("roles", []),
        ])
        s = score(hay)
        if s > 0:
            pid = "P:" + normalize(p.get("name", ""))
            bits = [
                "Feminino" if p.get("gender") == "F" else "Masculino" if p.get("gender") == "M" else None,
                f"n. {p.get('birth')}" if p.get("birth") else None,
                ", ".join(p.get("roles", [])) or p.get("role") or None,
            ]
            bits = [b for b in bits if b]
            hits.append({
                "kind": "person",
                "id": pid,
                "label": p.get("name", ""),
                "detail": " · ".join(bits) if bits else None,
                "link": f"#person={quote(pid)}",
                "_s": s,
            })
    
    # Search relations
    for r in relations:
        hay = " ".join([
            r.get("from", ""),
            r.get("to", ""),
            r.get("relation", ""),
            r.get("attribute", ""),
        ])
        s = score(hay)
        if s > 0:
            hits.append({
                "kind": "relation",
                "id": f"{r.get('from')}→{r.get('to')}",
                "label": f"{r.get('from')} {r.get('relation') or r.get('attribute') or '→'} {r.get('to')}",
                "detail": r.get("attribute"),
                "link": f"#person={quote('P:' + normalize(r.get('from', '')))}",
                "_s": s,
            })
    
    # Search documents
    for d in documents:
        hay = " ".join([
            d.get("id", ""),
            d.get("title", ""),
            d.get("document_type", ""),
            " ".join(d.get("document_date", [])),
            " ".join(d.get("entities", {}).get("names", [])),
        ])
        s = score(hay)
        if s > 0:
            hits.append({
                "kind": "document",
                "id": "DL:" + d.get("id", ""),
                "label": d.get("title") or d.get("id", ""),
                "detail": " · ".join([
                    d.get("document_type", ""),
                    "; ".join(d.get("document_date", [])),
                ]).strip(" · "),
                "link": f"#doc={quote('DL:' + d.get('id', ''))}",
                "_s": s,
            })
    
    # Sort by score and limit to top 25
    hits.sort(key=lambda h: h["_s"], reverse=True)
    top = hits[:25]
    top = [dict((k, v) for k, v in h.items() if k != "_s") for h in top]
    
    counts = {
        "person": len([h for h in top if h["kind"] == "person"]),
        "relation": len([h for h in top if h["kind"] == "relation"]),
        "document": len([h for h in top if h["kind"] == "document"]),
    }
    
    if not top:
        answer = f'No results found for "{question}". Try a person name, document type, or relation.'
    else:
        parts = []
        if counts["person"]:
            parts.append(f"{counts['person']} person(s)")
        if counts["relation"]:
            parts.append(f"{counts['relation']} relation(s)")
        if counts["document"]:
            parts.append(f"{counts['document']} document(s)")
        answer = f'Found {", ".join(parts)} for "{question}". Select a result to open it in the app.'
    
    return {"answer": answer, "hits": top}


# ========== Routes ==========

@app.route("/api/projects", methods=["GET"])
def api_list_projects():
    """List all projects."""
    return jsonify({"projects": list_projects()})


@app.route("/api/projects", methods=["POST"])
def api_create_project():
    """Create a new project."""
    try:
        body = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400
    
    if not body:
        body = {}
    
    name = safe_name(body.get("name", ""))
    if not name:
        return jsonify({"error": "Invalid name (use letters, numbers, - or _)"}), 400
    
    res = create_project(name, body.get("displayName"))
    if not res["ok"]:
        return jsonify({"error": res["error"]}), 409
    return jsonify({"ok": True, "name": name})


@app.route("/api/projects/<name>", methods=["DELETE"])
def api_delete_project(name):
    """Delete a project directory and all of its contents."""
    name = safe_name(name)
    if not name:
        return jsonify({"error": "Invalid project"}), 400

    project_dir = PROJECTS_DIR / name
    if not project_dir.exists() or not project_dir.is_dir():
        return jsonify({"error": "Project does not exist"}), 404

    try:
        shutil.rmtree(project_dir)
    except OSError as error:
        return jsonify({"error": f"Could not delete project: {error}"}), 500
    return jsonify({"ok": True, "name": name})


@app.route("/api/projects/<name>/upload", methods=["POST"])
def api_upload(name):
    """Upload files to a project."""
    name = safe_name(name)
    if not name:
        return jsonify({"error": "Invalid project"}), 400
    
    project_dir = PROJECTS_DIR / name
    if not project_dir.exists():
        return jsonify({"error": "Project does not exist"}), 404
    
    imported_dir = project_dir / "imported"
    imported_dir.mkdir(parents=True, exist_ok=True)
    
    if "files" not in request.files:
        return jsonify({"error": "No files provided"}), 400
    
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided"}), 400
    
    saved = []
    skipped = []
    for f in files:
        if not f.filename:
            continue
        # Keep only basename; ignore folder structure from drag-drop
        fname = Path(f.filename).name
        if not re.search(r"\.(jpe?g|png|gif|webp|pdf)$", fname, re.IGNORECASE):
            skipped.append(fname)
            continue
        dest = imported_dir / fname
        f.save(str(dest))
        saved.append(fname)
    
    return jsonify({"ok": True, "saved": saved, "skipped": skipped, "total": len(saved)})


@app.route("/api/projects/<name>/data", methods=["GET"])
def api_project_data(name):
    """Get project's docs_logical.json."""
    name = safe_name(name)
    if not name:
        return jsonify({"error": "Invalid project"}), 400
    
    data = load_project_data(name)
    if not data:
        return jsonify({"error": "No project data"}), 404
    return jsonify(data)


@app.route("/api/projects/<name>/details", methods=["GET"])
def api_project_details(name):
    """Get file and processing status for a project."""
    name = safe_name(name)
    if not name:
        return jsonify({"error": "Invalid project"}), 400
    project_dir = PROJECTS_DIR / name
    if not project_dir.exists():
        return jsonify({"error": "Project does not exist"}), 404
    return jsonify(project_details(project_dir))


@app.route("/api/projects/<name>/glossary", methods=["GET", "PUT"])
def api_project_glossary(name):
    """Read or save the project's GLOSSARIO.md file."""
    name = safe_name(name)
    if not name:
        return jsonify({"error": "Invalid project"}), 400
    project_dir = PROJECTS_DIR / name
    if not project_dir.exists():
        return jsonify({"error": "Project does not exist"}), 404
    glossary_path = project_dir / "GLOSSARIO.md"
    if request.method == "GET":
        return jsonify({"content": glossary_path.read_text(encoding="utf-8") if glossary_path.exists() else ""})

    body = request.get_json(silent=True) or {}
    content = body.get("content")
    if not isinstance(content, str):
        return jsonify({"error": "Invalid content"}), 400
    glossary_path.write_text(content, encoding="utf-8")
    return jsonify({"ok": True})


@app.route("/api/projects/<name>/file/<file_name>", methods=["GET", "PUT"])
def api_project_file(name, file_name):
    """Read or save one whitelisted Build Metadata project file."""
    name = safe_name(name)
    allowed = {
        "GLOSSARIO.md": False,
        "docs_logical_map.json": True,
        "docs_logical.json": True,
        "gender_rules.json": True,
    }
    if not name:
        return jsonify({"error": "Invalid project"}), 400
    if file_name not in allowed:
        return jsonify({"error": "Project file is not editable"}), 400
    project_dir = PROJECTS_DIR / name
    if not project_dir.exists():
        return jsonify({"error": "Project does not exist"}), 404
    file_path = project_dir / file_name

    if request.method == "GET":
        return jsonify({
            "file": file_name,
            "content": file_path.read_text(encoding="utf-8") if file_path.exists() else "",
        })

    body = request.get_json(silent=True) or {}
    content = body.get("content")
    if not isinstance(content, str):
        return jsonify({"error": "Invalid content"}), 400
    if allowed[file_name]:
        try:
            json.loads(content)
        except json.JSONDecodeError as error:
            return jsonify({"error": f"Invalid JSON: {error.msg}"}), 400
    file_path.write_text(content, encoding="utf-8")
    return jsonify({"ok": True, "file": file_name})


@app.route("/api/projects/<name>/process", methods=["POST"])
def api_project_process(name):
    """Run a named processing operation locally or via the configured GenAI runner."""
    name = safe_name(name)
    if not name:
        return jsonify({"error": "Invalid project"}), 400
    project_dir = PROJECTS_DIR / name
    if not project_dir.exists():
        return jsonify({"error": "Project does not exist"}), 404

    mode = (request.get_json(silent=True) or {}).get("mode", "")
    if mode not in ("ocr", "reinterpret", "build", "map", "validate-docs"):
        return jsonify({"error": "Invalid processing mode"}), 400

    if mode == "build":
        commands = [
            ["python3", str(ROOT / "skills/transcript/build_docs_logical.py"), str(project_dir)],
        ]
    elif mode == "validate-docs":
        commands = [
            ["python3", str(ROOT / "skills/transcript/validate_docs.py"), str(project_dir)],
        ]
    else:
        runner = os.environ.get("NOTARYMIND_GENAI_RUNNER", "").strip()
        if not runner:
            return jsonify({
                "error": "GenAI processing is not configured on the server",
                "mode": mode,
                "model": GENAI_MODEL,
                "hint": "Set NOTARYMIND_GENAI_RUNNER to an executable that accepts: <mode> <project_path> <model>.",
            }), 503
        commands = [[runner, mode, str(project_dir), GENAI_MODEL]]

    output = []
    try:
        for command in commands:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300, check=False)
            output.append((result.stdout + result.stderr).strip())
            if result.returncode != 0:
                return jsonify({"error": "Processing failed", "mode": mode, "output": "\n".join(output)}), 422
    except (OSError, subprocess.TimeoutExpired) as error:
        return jsonify({"error": str(error), "mode": mode}), 500

    return jsonify({"ok": True, "mode": mode, "model": GENAI_MODEL if mode != "build" else None, "output": "\n".join(output)})


@app.route("/api/projects/<name>/tools", methods=["POST"])
def api_project_tools(name):
    """Run a read-only project audit or validator and return its report."""
    name = safe_name(name)
    if not name:
        return jsonify({"error": "Invalid project"}), 400
    project_dir = PROJECTS_DIR / name
    if not project_dir.exists():
        return jsonify({"error": "Project does not exist"}), 404

    tool = (request.get_json(silent=True) or {}).get("tool", "")
    scripts = {
        "audit-inference": "audit_inference.py",
        "validate-map": "validate_map.py",
        "validate-variants": "validate_variants.py",
    }
    script = scripts.get(tool)
    if not script:
        return jsonify({"error": "Invalid project tool"}), 400

    command = ["python3", str(ROOT / "skills/transcript" / script), str(project_dir)]
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return jsonify({"error": str(error), "tool": tool}), 500

    output = (result.stdout + result.stderr).strip()
    return jsonify({
        "ok": result.returncode == 0,
        "tool": tool,
        "exitCode": result.returncode,
        "output": output,
    })


@app.route("/api/projects/<name>/raw", methods=["GET"])
def api_project_raw(name):
    """Read a file within a project (metadata/, imported/, etc.)."""
    name = safe_name(name)
    if not name:
        return jsonify({"error": "Invalid project"}), 400
    
    rel = request.args.get("path", "")
    abs_path = safe_join(PROJECTS_DIR / name, rel)
    if not abs_path:
        return jsonify({"error": "Invalid path"}), 400
    
    if not abs_path.exists():
        return jsonify({"error": "Not found"}), 404
    
    if abs_path.is_dir():
        return jsonify({"error": "Path is a directory"}), 400
    
    # Serve the file
    if abs_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf"):
        return send_file(str(abs_path))
    elif abs_path.suffix.lower() == ".json":
        return send_file(str(abs_path), mimetype="application/json")
    else:
        return send_file(str(abs_path))


@app.route("/api/agent/query", methods=["POST"])
def api_agent_query():
    """Query-only agent endpoint."""
    try:
        body = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400
    
    if not body:
        body = {}
    
    project = safe_name(body.get("project", "")) or "cotimos"
    question = str(body.get("question", ""))[:500].strip()
    
    if not question:
        return jsonify({"error": "Question is empty"}), 400
    
    result = agent_query(project, question)
    result["project"] = project
    result["readonly"] = True
    return jsonify(result)


@app.route("/", methods=["GET"])
@app.route("/ui", methods=["GET"])
@app.route("/ui/", methods=["GET"])
def serve_ui_main():
    """Serve main.html."""
    return send_file(str(UI_DIR / "main.html"), mimetype="text/html")


@app.route("/ui/<path:subpath>", methods=["GET"])
def serve_ui(subpath):
    """Serve files from ui/ directory."""
    abs_path = safe_join(UI_DIR, "/" + subpath)
    if not abs_path or not abs_path.exists():
        return jsonify({"error": "Not found"}), 404
    if abs_path.is_dir():
        return jsonify({"error": "Path is a directory"}), 400
    return send_file(str(abs_path))


@app.route("/projects/<name>/<path:subpath>", methods=["GET"])
def serve_project_files(name, subpath):
    """Serve files from project directories (imported/, metadata/, etc.)."""
    name = safe_name(name)
    if not name:
        return jsonify({"error": "Invalid project"}), 400
    
    abs_path = safe_join(PROJECTS_DIR / name, "/" + subpath)
    if not abs_path or not abs_path.exists():
        return jsonify({"error": "Not found"}), 404
    if abs_path.is_dir():
        return jsonify({"error": "Path is a directory"}), 400
    return send_file(str(abs_path))


if __name__ == "__main__":
    print(f"NotaryMindAi API on http://localhost:{PORT}")
    print(f"  UI:        http://localhost:{PORT}/")
    print(f"  Projects:  {PROJECTS_DIR}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
