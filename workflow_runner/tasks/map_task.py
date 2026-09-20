"""External map-generation task prompt and schema contract for the runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workflow_runner.common import (
    RunnerError,
    _atomic_json,
    _glossary,
    _metadata_files,
    _read_json,
    _request_json,
)

MAP_TASK = """You are creating the logical document map for a project from image metadata and transcripts.

Use only evidence in the supplied project metadata, glossary, and existing map. Do not modify metadata files. Return only a JSON object with schema_version and logical_documents.

Each logical document must have id, title, type, and images. Use only image names present in the metadata. Preserve stable existing ids where possible. Keep the output schema compliant with the project's logical document format.

Use the project glossary as a reading aid for names, variants, and local normalization, but do not invent document grouping, titles, or identities beyond the evidence. Keep mapping deterministic and grounded in source metadata.
"""

MAP_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "logical_documents"],
    "properties": {
        "schema_version": {"type": "string"},
        "logical_documents": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "title", "type", "images"],
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "type": {"type": "string"},
                    "images": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


def run_map(project: Path, model: str) -> dict[str, Any]:
    metadata = [_read_json(path) for path in _metadata_files(project)]
    existing_path = project / "docs_logical_map.json"
    existing = _read_json(existing_path) if existing_path.exists() else {"schema_version": "2.0", "logical_documents": []}
    prompt = f"""{MAP_TASK}

Existing map:
{json.dumps(existing, ensure_ascii=False)}
Metadata transcripts and extracted fields:
{json.dumps(metadata, ensure_ascii=False)}
Glossary:
{_glossary(project)}"""
    result = _request_json([{"role": "user", "content": prompt}], model)
    if not isinstance(result, dict) or not isinstance(result.get("logical_documents"), list):
        raise RunnerError("map result must contain a logical_documents array")
    available = {item.get("image") for item in metadata}
    seen = set()
    for document in result["logical_documents"]:
        if not isinstance(document, dict) or not document.get("id") or not document.get("images"):
            raise RunnerError("map contains a document without id or images")
        for image in document["images"]:
            if image not in available:
                raise RunnerError(f"map references unknown image: {image}")
            if image in seen:
                raise RunnerError(f"image appears in more than one logical document: {image}")
            seen.add(image)
    result["schema_version"] = "2.0"
    _atomic_json(existing_path, result)
    return {"operation": "map", "model": model, "documents": len(result["logical_documents"]), "images_mapped": len(seen), "files_written": [existing_path.name]}


__all__ = ["MAP_TASK", "MAP_SCHEMA", "run_map"]
