"""External map-generation task prompt and schema contract for the runner."""

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
