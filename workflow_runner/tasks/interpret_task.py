"""External interpretation task prompt and schema contract for the runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workflow_runner.common import (
    RunnerError,
    RELATION_GUIDE,
    CANONICAL_RELATION_TYPES,
    _atomic_json,
    _glossary,
    _metadata_files,
    _read_json,
    _request_json,
)

INTERPRET_TASK = """You are interpreting an already-extracted historical document transcript.

Use only evidence in the supplied transcript, glossary, and project metadata. Preserve the original full_transcript exactly. Update only the structured interpretation fields. Never invent names, dates, values, or relations. Use empty values or '[?]' when evidence is unavailable. Return JSON only, without Markdown.

Return JSON matching this exact metadata shape. Preserve the image, full_transcript, ocr_metadata from the source metadata. Fill the structured fields for entities, properties, persons, and relations from the document evidence. Keep the original transcript intact and do not rewrite it.

Example shape:
{
  "image": "<name>.jpg",
  "document_type": "string",
  "document_date": "string or array",
  "location": "string or array",
  "full_transcript": "string",
  "entities": {
    "names": ["string"],
    "dates": ["string"],
    "places": ["string"],
    "values": ["string"]
  },
  "properties": [{
    "description": "string",
    "location": "string",
    "article": "string",
    "quota": "string",
    "value": "string",
    "confrontations": {"north": "string", "south": "string", "east": "string", "west": "string"},
    "_source": "<name>.jpg"
  }],
  "persons": [{
    "name": "string",
    "roles": ["string"],
    "variants": [],
    "birthplace": "string"
  }],
  "relations": [{
    "from": "string",
    "to": "string",
    "relation": "string",
    "attribute": "sale|marriage|inheritance|...",
    "property": "string"
  }],
  "ocr_metadata": {
    "genai_model": "string",
    "method": "string",
    "status": "string",
    "notes": "string"
  }
}

Use the project glossary as a reading aid to normalize known variants and local names only when supported by the document. Provide the best supported structured interpretation without altering the source transcript.

{relation_guide}
""".replace("{relation_guide}", RELATION_GUIDE)

INTERPRET_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
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
        "image": {"type": ["string", "null"]},
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
        "ocr_metadata": {"type": "object"},
    },
}


def _validate_interpret_result(result: Any, *, current: dict[str, Any], image_name: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise RunnerError("Interpretation result must be a JSON object")

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
        raise RunnerError(f"Interpretation missing required fields: {', '.join(missing)}")

    if result.get("image") not in {None, current.get("image"), image_name, image_name.rsplit(".", 1)[0] + ".jpg"}:
        raise RunnerError("Interpretation returned an invalid image identity")

    entities = result.get("entities")
    if not isinstance(entities, dict):
        raise RunnerError("Interpretation entities must be an object")
    for key in ("names", "dates", "places", "values"):
        if key not in entities or not isinstance(entities[key], list):
            raise RunnerError(f"Interpretation entities.{key} must be an array")

    if not isinstance(result.get("ocr_metadata"), dict):
        raise RunnerError("Interpretation ocr_metadata must be an object")

    properties = result.get("properties")
    if not isinstance(properties, list):
        raise RunnerError("Interpretation properties must be an array")
    for idx, prop in enumerate(properties):
        if not isinstance(prop, dict):
            raise RunnerError(f"Interpretation properties[{idx}] must be an object")
        for key in ("description", "location", "article", "quota", "value"):
            if key not in prop:
                raise RunnerError(f"Interpretation properties[{idx}] missing {key}")
        if "confrontations" in prop and not isinstance(prop["confrontations"], dict):
            raise RunnerError(f"Interpretation properties[{idx}].confrontations must be an object")

    persons = result.get("persons")
    if not isinstance(persons, list):
        raise RunnerError("Interpretation persons must be an array")
    for idx, person in enumerate(persons):
        if not isinstance(person, dict):
            raise RunnerError(f"Interpretation persons[{idx}] must be an object")
        if "name" not in person or not isinstance(person["name"], str):
            raise RunnerError(f"Interpretation persons[{idx}].name must be a string")
        if "roles" not in person or not isinstance(person["roles"], list):
            raise RunnerError(f"Interpretation persons[{idx}].roles must be an array")

    relations = result.get("relations")
    if not isinstance(relations, list):
        raise RunnerError("Interpretation relations must be an array")
    for idx, relation in enumerate(relations):
        if not isinstance(relation, dict):
            raise RunnerError(f"Interpretation relations[{idx}] must be an object")
        for key in ("from", "to", "relation", "attribute"):
            if key not in relation:
                raise RunnerError(f"Interpretation relations[{idx}] missing {key}")
        if relation["attribute"] not in CANONICAL_RELATION_TYPES:
            raise RunnerError(f"Interpretation relations[{idx}].attribute is not a canonical relation type: {relation['attribute']}")

    result["image"] = current.get("image", image_name)
    result["full_transcript"] = current.get("full_transcript", result.get("full_transcript", ""))
    return result


def run_interpret(project: Path, model: str, *, only_new: bool = False) -> dict[str, Any]:
    metadata_files = _metadata_files(project)
    if only_new:
        imported = sorted(
            p for p in (project / "imported").iterdir()
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".pdf"}
        )
        by_stem = {image.stem: image for image in imported}
        filtered: list[Path] = []
        for path in metadata_files:
            image = by_stem.get(path.stem)
            if image is None:
                continue
            try:
                if image.stat().st_mtime > path.stat().st_mtime:
                    filtered.append(path)
            except OSError:
                filtered.append(path)
        metadata_files = filtered

    written = []
    failures = []
    for path in metadata_files:
        try:
            current = _read_json(path)
            transcript = current.get("full_transcript", "")
            if not transcript:
                raise RunnerError("full_transcript is empty")
            prompt = f"{INTERPRET_TASK}\n\nExisting metadata:\n{json.dumps(current, ensure_ascii=False)}\nGlossary:\n{_glossary(project)}"
            result = _request_json([{"role": "user", "content": prompt}], model)
            validated = _validate_interpret_result(result, current=current, image_name=path.name)
            validated["full_transcript"] = transcript
            preserved_metadata = current.get("ocr_metadata", {}) if isinstance(current.get("ocr_metadata"), dict) else {}
            merged_metadata = {**preserved_metadata, **(validated.get("ocr_metadata") or {})}
            merged_metadata["genai_model"] = model
            merged_metadata["method"] = "workflow_runner.interpret"
            validated["ocr_metadata"] = merged_metadata
            _atomic_json(path, validated)
            written.append(path.name)
        except RunnerError as error:
            failures.append({"file": path.name, "error": str(error)})
    return {"operation": "interpret", "model": model, "processed": len(written), "failed": failures, "files_written": written}


__all__ = ["INTERPRET_TASK", "INTERPRET_SCHEMA", "run_interpret"]
