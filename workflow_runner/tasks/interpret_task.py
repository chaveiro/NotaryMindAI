"""External interpretation task prompt and schema contract for the runner."""

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
