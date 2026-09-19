#!/usr/bin/env python3
"""Variant conflict detection tool.

Scans a project for person name conflicts and suggests GLOSSARIO entries.

Usage:
    python3 validate_variants.py /path/to/project

Output:
    - Potential duplicates (fuzzy/prefix matches)
    - Confidence levels for each suggestion
    - Suggested GLOSSARIO.md entries
"""

import json
import os
import sys
import re
import unicodedata
from difflib import SequenceMatcher

def _norm(s):
    """Normalize name for comparison."""
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()

def _similarity(a, b):
    """Compute similarity ratio (0-1)."""
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()

def load_persons(project_path):
    """Load all persons from metadata JSONs."""
    metadata_dir = os.path.join(project_path, "metadata")
    persons = []
    
    if not os.path.isdir(metadata_dir):
        print(f"Metadata directory not found: {metadata_dir}", file=sys.stderr)
        return persons
    
    for filename in sorted(os.listdir(metadata_dir)):
        if not filename.endswith(".json"):
            continue
        
        filepath = os.path.join(metadata_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Support both new (top-level) and old (genealogy wrapper) formats
            persons_data = data.get("persons") or (data.get("genealogy") or {}).get("persons") or []
            
            for person in persons_data:
                name = person.get("name")
                if name:
                    persons.append({
                        "name": name,
                        "source": filename,
                        "roles": person.get("roles", person.get("role", [])),
                        "variants": person.get("variants", [])
                    })
        except Exception as e:
            print(f"Error reading {filename}: {e}", file=sys.stderr)
    
    return persons

def detect_conflicts(persons):
    """Detect potential variant conflicts."""
    conflicts = []
    
    # Group by normalized name
    by_norm = {}
    for person in persons:
        norm_name = _norm(person["name"])
        if norm_name not in by_norm:
            by_norm[norm_name] = []
        by_norm[norm_name].append(person)
    
    # Check for exact normalized matches
    for norm_name, group in by_norm.items():
        if len(group) > 1:
            distinct_names = list(set(p["name"] for p in group))
            if len(distinct_names) > 1:
                conflicts.append({
                    "type": "exact_match",
                    "canonical": distinct_names[0],
                    "variants": distinct_names[1:],
                    "confidence": "very_high",
                    "instances": group
                })
    
    # Check for prefix/fuzzy matches (high similarity)
    seen = set()
    for i, p1 in enumerate(persons):
        norm1 = _norm(p1["name"])
        if norm1 in seen:
            continue
        
        for p2 in persons[i+1:]:
            norm2 = _norm(p2["name"])
            if norm2 in seen or norm1 == norm2:
                continue
            
            similarity = _similarity(p1["name"], p2["name"])
            
            # Prefix match (one is substring of other)
            if norm1 in norm2 or norm2 in norm1:
                conflicts.append({
                    "type": "prefix_match",
                    "name1": p1["name"],
                    "name2": p2["name"],
                    "confidence": "high",
                    "suggestion": f'Possibly same person (prefix match)',
                    "instances": [p1, p2]
                })
                seen.add(norm2)
            
            # High fuzzy similarity (>80%)
            elif similarity > 0.80:
                conflicts.append({
                    "type": "fuzzy_match",
                    "name1": p1["name"],
                    "name2": p2["name"],
                    "similarity": similarity,
                    "confidence": "medium",
                    "suggestion": f'Possibly same person (fuzzy match, {similarity*100:.0f}% similar)',
                    "instances": [p1, p2]
                })
                seen.add(norm2)

    return conflicts

def print_report(conflicts):
    """Pretty-print conflict report."""
    print("\n" + "="*70)
    print("VARIANT CONFLICT REPORT")
    print("="*70 + "\n")
    
    if not conflicts:
        print("✅ No conflicts found!")
        return
    
    # Group by type
    by_type = {}
    for conflict in conflicts:
        type_name = conflict["type"]
        if type_name not in by_type:
            by_type[type_name] = []
        by_type[type_name].append(conflict)
    
    for type_name, group in sorted(by_type.items()):
        print(f"\n📋 {type_name.upper()} ({len(group)} found)")
        print("-" * 70)
        
        for i, conflict in enumerate(group, 1):
            if type_name == "exact_match":
                print(f"\n  {i}. EXACT NORMALIZED MATCH")
                print(f"     Canonical: {conflict['canonical']}")
                for variant in conflict["variants"]:
                    print(f"     Variant:   {variant}")
                print(f"     Confidence: {conflict['confidence']}")
                print(f"     Found in: {len(conflict['instances'])} places")
                
                # Print GLOSSARIO suggestion
                all_names = [conflict['canonical']] + conflict['variants']
                print(f"\n     Suggested GLOSSARIO entry:")
                print(f"     - **{all_names[0]}** — NOT \"{'\", \"'.join(all_names[1:])}\"")
                print(f"     Always correct to canonical form")
                print(f"     ```json")
                print(f"     {{ \"identities\": {json.dumps(all_names)} }}")
                print(f"     ```")
            else:
                print(f"\n  {i}. {conflict.get('type', 'UNKNOWN')}")
                print(f"     Name 1: {conflict['name1']}")
                print(f"     Name 2: {conflict['name2']}")
                if "similarity" in conflict:
                    print(f"     Similarity: {conflict['similarity']*100:.0f}%")
                print(f"     Confidence: {conflict['confidence']}")
                print(f"     Status: {conflict.get('suggestion', 'MANUAL REVIEW NEEDED')}")
    
    print("\n" + "="*70)
    print(f"Total conflicts: {len(conflicts)}")
    print("="*70 + "\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_variants.py /path/to/project")
        sys.exit(1)
    
    project_path = sys.argv[1]
    
    print(f"Loading persons from {project_path}...")
    persons = load_persons(project_path)
    print(f"✓ Loaded {len(persons)} persons")
    
    print("Detecting conflicts...")
    conflicts = detect_conflicts(persons)
    
    print_report(conflicts)
    
    return 0  # findings are reported in stdout, not via exit code (keeps API/UI calls from treating this as a failure)

if __name__ == "__main__":
    sys.exit(main())
