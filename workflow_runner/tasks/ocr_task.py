"""External OCR task prompt and schema contract for the runner."""

OCR_TASK = """You are extracting the raw archival transcription from one historical image or PDF page.

Use only evidence in the supplied image, transcript, glossary, or project files. Never invent names, dates, values, or relations. Use empty values or '[?]' when evidence is unavailable. Return JSON only, without Markdown.

Return a minimal OCR object with these keys:
{
  "image": string,
  "document_type": string,
  "document_date": string or array,
  "location": string or array,
  "full_transcript": string,
  "entities": {"names": [], "dates": [], "places": [], "values": []},
  "properties": [],
  "persons": [],
  "relations": [],
  "ocr_metadata": {"status": string, "notes": string}
}

This task is for low-level extraction only. It should capture the OCR transcript and basic metadata, not the final structured interpretation. Leave entities, properties, persons, and relations empty unless they are directly evidenced and unavoidable.

Use the project glossary as a reading aid to resolve names, variants, and local normalization only when supported by the document. Keep the source text faithful to the image; do not silently normalize beyond the glossary.
"""

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
