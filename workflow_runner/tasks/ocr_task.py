"""External OCR task prompt and schema contract for the runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workflow_runner.common import (
    RunnerError,
    RELATION_GUIDE,
    CANONICAL_RELATION_TYPES,
    SUPPORTED_EXTENSIONS,
    _atomic_json,
    _glossary,
    _metadata_files,
    _read_json,
    _request_json,
)

OCR_TASK = """You are extracting the raw archival transcription from one historical image or PDF page.

Use only evidence in the supplied image, transcript, glossary, or project files. Never invent names, dates, values, or relations. Use empty values or '[?]' when evidence is unavailable. Return JSON only, without Markdown.

Return JSON matching this shape with these keys:
{
  "image": string,
  "document_type": string,
  "document_date": string or array,
  "location": string or array,
  "full_transcript": string,
  "entities": {"names": [], "dates": [], "places": [], "values": []},
  "properties": [
    {"description": "string", "location": "string", "article": "string", "quota": "string", "value": "string", "confrontations": {"north": "string", "south": "string", "east": "string", "west": "string"}, "_source": "file.jpg"}
  ],
  "persons": [
    {"name": "string", "roles": ["string"], "variants": [], "birthplace": "string"}
  ],
  "relations": [
    {"from": "string", "to": "string", "relation": "string", "attribute": "sale|marriage|inheritance|..."}
  ],
  "ocr_metadata": {"status": string, "notes": string}
}

This task is for low-level extraction only. It should capture the OCR full transcript and basic metadata, not the final structured interpretation. Leave entities, properties, persons, and relations empty unless they are directly evidenced and unavoidable.

Use the project glossary as a reading aid to resolve names, variants, and local normalization only when supported by the document. Keep the source text faithful to the image; do not silently normalize beyond the glossary.

{relation_guide}
""".replace("{relation_guide}", RELATION_GUIDE)

OCR_SCHEMA = {
    "type": "object",
    "required": [
        "image",
        "document_type",
        "document_date",
        "location",
        "full_transcript",
        "entities",
        "properties",
        "persons",
        "relations",
        "ocr_metadata",
    ],
    "properties": {
        "image": {"type": "string"},
        "document_type": {"type": "string"},
        "document_date": {"type": ["string", "array"]},
        "location": {"type": ["string", "array"]},
        "full_transcript": {"type": "string"},
        "entities": {
            "type": "object",
            "required": ["names", "dates", "places", "values"],
            "properties": {
                "names": {"type": "array"},
                "dates": {"type": "array"},
                "places": {"type": "array"},
                "values": {"type": "array"},
            },
        },
        "properties": {"type": "array"},
        "persons": {"type": "array"},
        "relations": {"type": "array"},
        "ocr_metadata": {
            "type": "object",
            "required": ["status", "notes"],
            "properties": {
                "status": {"type": "string"},
                "notes": {"type": "string"},
            },
        },
    },
}


def _validate_ocr_result(result: Any, *, image_name: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise RunnerError("OCR result must be a JSON object")

    required = [
        "image",
        "document_type",
        "document_date",
        "location",
        "full_transcript",
        "entities",
        "properties",
        "persons",
        "relations",
        "ocr_metadata",
    ]
    missing = [key for key in required if key not in result]
    if missing:
        raise RunnerError(f"OCR missing required fields: {', '.join(missing)}")

    entities = result.get("entities")
    if not isinstance(entities, dict):
        raise RunnerError("OCR entities must be an object")
    for key in ("names", "dates", "places", "values"):
        if key not in entities or not isinstance(entities[key], list):
            raise RunnerError(f"OCR entities.{key} must be an array")

    if not isinstance(result.get("ocr_metadata"), dict):
        raise RunnerError("OCR ocr_metadata must be an object")

    properties = result.get("properties")
    if not isinstance(properties, list):
        raise RunnerError("OCR properties must be an array")
    for idx, prop in enumerate(properties):
        if not isinstance(prop, dict):
            raise RunnerError(f"OCR properties[{idx}] must be an object")
        for key in ("description", "location", "article", "quota", "value"):
            if key not in prop:
                raise RunnerError(f"OCR properties[{idx}] missing {key}")
        confrontations = prop.get("confrontations", {})
        if not isinstance(confrontations, dict):
            raise RunnerError(f"OCR properties[{idx}].confrontations must be an object")

    persons = result.get("persons")
    if not isinstance(persons, list):
        raise RunnerError("OCR persons must be an array")
    for idx, person in enumerate(persons):
        if not isinstance(person, dict):
            raise RunnerError(f"OCR persons[{idx}] must be an object")
        if "name" not in person or not isinstance(person["name"], str):
            raise RunnerError(f"OCR persons[{idx}].name must be a string")
        if "roles" not in person or not isinstance(person["roles"], list):
            raise RunnerError(f"OCR persons[{idx}].roles must be an array")

    relations = result.get("relations")
    if not isinstance(relations, list):
        raise RunnerError("OCR relations must be an array")
    for idx, relation in enumerate(relations):
        if not isinstance(relation, dict):
            raise RunnerError(f"OCR relations[{idx}] must be an object")
        for key in ("from", "to", "relation", "attribute"):
            if key not in relation:
                raise RunnerError(f"OCR relations[{idx}] missing {key}")
        if relation["attribute"] not in CANONICAL_RELATION_TYPES:
            raise RunnerError(f"OCR relations[{idx}].attribute is not a canonical relation type: {relation['attribute']}")

    result["image"] = image_name
    return result


def run_ocr(project: Path, model: str, *, only_new: bool = False) -> dict[str, Any]:
    imported = sorted(p for p in (project / "imported").iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS)
    metadata = project / "metadata"
    metadata.mkdir(exist_ok=True)
    targets = imported
    if only_new:
        targets = []
        for image in imported:
            metadata_path = metadata / f"{image.stem}.json"
            if not metadata_path.exists():
                targets.append(image)
                continue
            try:
                if image.stat().st_mtime > metadata_path.stat().st_mtime:
                    targets.append(image)
            except OSError:
                targets.append(image)
    written = []
    failures = []
    for image in targets:
        try:
            prompt = f"{OCR_TASK}\n\nGlossary:\n{_glossary(project)}"
            result = _request_json([{"role": "user", "content": prompt}], model, image)
            validated = _validate_ocr_result(result, image_name=image.name)
            validated.setdefault("ocr_metadata", {})["genai_model"] = model
            validated["ocr_metadata"]["method"] = "workflow_runner.ocr"
            _atomic_json(metadata / f"{image.stem}.json", validated)
            written.append(image.name)
        except RunnerError as error:
            failures.append({"file": image.name, "error": str(error)})
    return {
        "operation": "ocr",
        "model": model,
        "processed": len(written),
        "skipped": len(imported) - len(targets),
        "failed": failures,
        "files_written": written,
    }


__all__ = ["OCR_TASK", "OCR_SCHEMA", "run_ocr"]
