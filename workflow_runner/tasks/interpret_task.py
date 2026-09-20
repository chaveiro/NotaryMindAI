"""External interpretation task prompt and schema contract for the runner."""

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

INTERPRET_TASK = """You are interpreting an already-extracted historical document transcript.

Use only evidence in the supplied transcript, glossary, and project metadata. Preserve the original full_transcript exactly. Update only the structured interpretation fields. Never invent names, dates, values, or relations. Use empty values or '[?]' when evidence is unavailable. Return JSON only, without Markdown.

Return the complete metadata object, preserving image and full_transcript. Fill the structured fields for entities, properties, persons, and relations from the document evidence. Keep the original transcript intact and do not rewrite it.

Use the project glossary as a reading aid to normalize known variants and local names only when supported by the document. Provide the best supported structured interpretation without altering the source transcript.
"""

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


def run_interpret(project: Path, model: str) -> dict[str, Any]:
    written = []
    failures = []
    for path in _metadata_files(project):
        try:
            current = _read_json(path)
            transcript = current.get("full_transcript", "")
            if not transcript:
                raise RunnerError("full_transcript is empty")
            prompt = f"{INTERPRET_TASK}\n\nExisting metadata:\n{json.dumps(current, ensure_ascii=False)}\nGlossary:\n{_glossary(project)}"
            result = _request_json([{"role": "user", "content": prompt}], model)
            if not isinstance(result, dict) or result.get("image") not in {None, current.get("image"), path.stem + ".jpg"}:
                raise RunnerError("interpretation returned an invalid image identity")
            result["image"] = current.get("image", result.get("image", path.stem + ".jpg"))
            result["full_transcript"] = transcript
            result.setdefault("ocr_metadata", {})["genai_model"] = model
            result["ocr_metadata"]["method"] = "workflow_runner.interpret"
            _atomic_json(path, result)
            written.append(path.name)
        except RunnerError as error:
            failures.append({"file": path.name, "error": str(error)})
    return {"operation": "interpret", "model": model, "processed": len(written), "failed": failures, "files_written": written}


__all__ = ["INTERPRET_TASK", "INTERPRET_SCHEMA", "run_interpret"]
