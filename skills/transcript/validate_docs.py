#!/usr/bin/env python3
"""
Validation of docs_logical.json — the final consolidated build output.

Unlike validate_map.py (which checks docs_logical_map.json, the intermediate
GenAI-authored map), this script checks the *output* of build_docs_logical.py:
required top-level keys, document/person integrity, dangling relation
endpoints, missing source files, and schema conformance (see SCHEMA.md).

Usage:
    python3 validate_docs.py /path/to/project
"""

import json
import sys
from pathlib import Path

KNOWN_ATTRIBUTES = {
    "filiation", "descent", "marriage", "kinship", "inheritance",
    "godparent", "sale", "mortgage", "other",
}
KNOWN_GENDER_SOURCES = {"explicit", "inferred", "context"}  # "context" is what build_docs_logical.py actually emits


def load_docs(project_path):
    docs_path = project_path / "docs_logical.json"
    if not docs_path.exists():
        print(f"docs_logical.json not found: {docs_path}", file=sys.stderr)
        sys.exit(1)
    with open(docs_path, encoding="utf-8") as f:
        return json.load(f)


def _norm(name):
    return " ".join((name or "").lower().split())


def check_top_level(data):
    issues = []
    for key in ("schema_version", "persons", "relations", "documents"):
        if key not in data:
            issues.append({"type": "missing_top_level_key", "msg": f"Missing top-level key: '{key}'"})
    return issues


def check_documents(data, project_path):
    issues = []
    seen_ids = set()
    metadata_dir = project_path / "metadata"
    for doc in data.get("documents", []):
        doc_id = doc.get("id")
        if not doc_id:
            issues.append({"type": "document_missing_id", "msg": f"Document missing 'id': {doc.get('title', '?')}"})
            continue
        if doc_id in seen_ids:
            issues.append({"type": "duplicate_document_id", "msg": f"Duplicate document id: {doc_id}"})
        seen_ids.add(doc_id)

        if not doc.get("sources"):
            issues.append({"type": "document_no_sources", "msg": f"{doc_id}: no 'sources' (no linked images)"})
        for source in doc.get("sources", []):
            json_file = source.get("json_file")
            if json_file and not (project_path / json_file).exists():
                issues.append({"type": "missing_source_metadata", "msg": f"{doc_id}: metadata file not found: {json_file}"})
            image = source.get("image")
            if image and metadata_dir.exists() and not (project_path / "imported" / image).exists():
                issues.append({"type": "missing_source_image", "msg": f"{doc_id}: imported image not found: {image}"})

        if not doc.get("document_type"):
            issues.append({"type": "document_missing_type", "msg": f"{doc_id}: missing 'document_type'"})
    return issues


def check_persons(data):
    issues = []
    seen_names = set()
    for person in data.get("persons", []):
        name = person.get("name")
        if not name:
            issues.append({"type": "person_missing_name", "msg": "Person entry missing 'name'"})
            continue
        key = _norm(name)
        if key in seen_names:
            issues.append({"type": "duplicate_person", "msg": f"Duplicate person name (post-GLOSSARIO): {name}"})
        seen_names.add(key)

        gender_source = person.get("gender_source")
        if gender_source and gender_source not in KNOWN_GENDER_SOURCES:
            issues.append({"type": "invalid_gender_source", "msg": f"{name}: unknown gender_source '{gender_source}'"})
        if gender_source and not person.get("gender"):
            issues.append({"type": "gender_source_without_gender", "msg": f"{name}: has gender_source but no gender"})

        if not person.get("source_images"):
            issues.append({"type": "person_no_sources", "msg": f"{name}: no 'source_images' (unreferenced person)"})
    return issues


def check_relations(data):
    issues = []
    persons = data.get("persons", [])
    known_names = set()
    for person in persons:
        known_names.add(_norm(person.get("name")))
        for variant in person.get("variants", []):
            variant_name = variant.get("name") if isinstance(variant, dict) else variant
            known_names.add(_norm(variant_name))

    for rel in data.get("relations", []):
        from_name, to_name = rel.get("from"), rel.get("to")
        if not from_name or not to_name:
            issues.append({"type": "relation_missing_endpoint", "msg": f"Relation missing from/to: {rel}"})
            continue
        if _norm(from_name) not in known_names:
            issues.append({"type": "relation_orphan_endpoint", "msg": f"Relation 'from' not found in persons: {from_name}"})
        if _norm(to_name) not in known_names:
            issues.append({"type": "relation_orphan_endpoint", "msg": f"Relation 'to' not found in persons: {to_name}"})

        attribute = rel.get("attribute")
        if attribute and attribute not in KNOWN_ATTRIBUTES:
            issues.append({"type": "unknown_relation_attribute", "msg": f"Unknown relation attribute '{attribute}' ({from_name} -> {to_name})"})
    return issues


def print_report(issues):
    print("\n" + "=" * 70)
    print("DOCS_LOGICAL.JSON VALIDATION REPORT")
    print("=" * 70 + "\n")

    if not issues:
        print("✅ No issues found! docs_logical.json is consistent.")
        return

    by_type = {}
    for issue in issues:
        by_type.setdefault(issue["type"], []).append(issue)

    for issue_type, group in sorted(by_type.items()):
        print(f"\n📋 {issue_type.upper()} ({len(group)})")
        print("-" * 70)
        for issue in group:
            print(f"  - {issue['msg']}")

    print("\n" + "=" * 70)
    print(f"Total issues: {len(issues)}")
    print("=" * 70 + "\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_docs.py /path/to/project")
        sys.exit(1)

    project_path = Path(sys.argv[1])
    data = load_docs(project_path)

    issues = []
    issues += check_top_level(data)
    issues += check_documents(data, project_path)
    issues += check_persons(data)
    issues += check_relations(data)

    print_report(issues)
    return 0  # findings are reported in stdout, not via exit code (keeps API/UI calls from treating this as a failure)


if __name__ == "__main__":
    sys.exit(main())
