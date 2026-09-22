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

Return JSON matching this shape:
{
  "schema_version": "2.0",
  "logical_documents": [
    {"id": "DL01", "title": "string", "type": "string", "images": ["<name>.jpg", "<name>.pdf"]}
  ]
}

Each logical document must have id, title, type, and images. Use only image names present in the metadata. Each image belongs to exactly one logical document. Preserve stable existing ids where possible. Keep the output schema compliant with the project's logical document format.

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


def _validate_map_result(result: Any, *, available: set[str]) -> set[str]:
    if not isinstance(result, dict) or not isinstance(result.get("logical_documents"), list):
        raise RunnerError("map result must contain a logical_documents array")
    seen: set[str] = set()
    ids: set[str] = set()
    for idx, document in enumerate(result["logical_documents"]):
        if not isinstance(document, dict):
            raise RunnerError(f"map logical_documents[{idx}] must be an object")
        for key in ("id", "title", "type", "images"):
            if key not in document:
                raise RunnerError(f"map logical_documents[{idx}] missing {key}")
        if not isinstance(document["id"], str) or not document["id"]:
            raise RunnerError(f"map logical_documents[{idx}].id must be a non-empty string")
        if document["id"] in ids:
            raise RunnerError(f"map contains duplicate logical document id: {document['id']}")
        ids.add(document["id"])
        images = document["images"]
        if not isinstance(images, list) or not images:
            raise RunnerError(f"map logical_documents[{idx}].images must be a non-empty array")
        for image in images:
            if image not in available:
                raise RunnerError(f"map references unknown image: {image}")
            if image in seen:
                raise RunnerError(f"image appears in more than one logical document: {image}")
            seen.add(image)
    return seen


def run_map(project: Path, model: str, *, only_new: bool = False) -> dict[str, Any]:
    metadata = [_read_json(path) for path in _metadata_files(project)]
    existing_path = project / "docs_logical_map.json"
    existing = _read_json(existing_path) if existing_path.exists() else {"schema_version": "2.0", "logical_documents": []}

    if only_new:
        existing_images = {
            image
            for document in existing.get("logical_documents", [])
            for image in document.get("images", [])
            if isinstance(image, str)
        }
        metadata = [item for item in metadata if item.get("image") not in existing_images]
        if not metadata:
            return {
                "operation": "map",
                "model": model,
                "documents": len(existing.get("logical_documents", [])),
                "images_mapped": len(existing_images),
                "files_written": [existing_path.name],
                "skipped": True,
            }

    prompt = f"""{MAP_TASK}

Existing map:
{json.dumps(existing, ensure_ascii=False)}
Metadata transcripts and extracted fields:
{json.dumps(metadata, ensure_ascii=False)}
Glossary:
{_glossary(project)}"""
    result = _request_json([{"role": "user", "content": prompt}], model)
    available = {item.get("image") for item in metadata}
    seen = _validate_map_result(result, available=available)
    result["schema_version"] = "2.0"

    if only_new:
        merged_documents = list(existing.get("logical_documents", []))
        merged_images = {
            image
            for document in merged_documents
            for image in document.get("images", [])
            if isinstance(image, str)
        }
        for document in result.get("logical_documents", []):
            new_images = [image for image in document.get("images", []) if image not in merged_images]
            if not new_images:
                continue
            merged_documents.append({**document, "images": new_images})
            merged_images.update(new_images)
        result = {"schema_version": "2.0", "logical_documents": merged_documents}

    _atomic_json(existing_path, result)
    return {"operation": "map", "model": model, "documents": len(result["logical_documents"]), "images_mapped": len(seen), "files_written": [existing_path.name]}


__all__ = ["MAP_TASK", "MAP_SCHEMA", "run_map"]
