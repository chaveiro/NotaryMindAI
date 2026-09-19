#!/usr/bin/env python3
"""Inference quality audit tool.

Generates report on inferred relations and their confidence levels.

Usage:
    python3 audit_inference.py /path/to/project

Output:
    - Summary statistics (explicit vs. inferred)
    - Breakdown by relation type
    - Breakdown by confidence level
    - List of all inferred relations
    - Suspicious inferences (low confidence + cross-doc)
"""

import json
import os
import sys

def load_docs_logical(project_path):
    """Load the consolidated docs_logical.json."""
    output_path = os.path.join(project_path, "docs_logical.json")
    
    if not os.path.exists(output_path):
        print(f"docs_logical.json not found: {output_path}", file=sys.stderr)
        print("Run: python3 build_docs_logical.py first", file=sys.stderr)
        sys.exit(1)
    
    with open(output_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_inferences(data):
    """Analyze inference patterns in relations."""
    relations = data.get("relations", [])
    
    # Categorize relations
    explicit = []
    inferred_agent = []  # inferedbyai: true
    inferred_build = []  # infered: true (from build script)
    
    for rel in relations:
        if rel.get("inferedbyai"):
            inferred_agent.append(rel)
        elif rel.get("source") == "inferred":
            inferred_build.append(rel)
        else:
            explicit.append(rel)
    
    # Breakdown by attribute type
    by_attribute = {}
    for rel in relations:
        attr = rel.get("attribute", "unknown")
        if attr not in by_attribute:
            by_attribute[attr] = {"explicit": 0, "inferred_agent": 0, "inferred_build": 0}
        
        if rel.get("inferedbyai"):
            by_attribute[attr]["inferred_agent"] += 1
        elif rel.get("source") == "inferred":
            by_attribute[attr]["inferred_build"] += 1
        else:
            by_attribute[attr]["explicit"] += 1
    
    # Breakdown by confidence
    confidence_dist = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    for rel in inferred_agent + inferred_build:
        conf = rel.get("inference_confidence", "unknown")
        if conf in confidence_dist:
            confidence_dist[conf] += 1
        else:
            confidence_dist["unknown"] += 1
    
    # Breakdown by inference type
    inference_types = {}
    for rel in inferred_agent + inferred_build:
        inf_type = rel.get("inference_type", "unknown")
        if inf_type not in inference_types:
            inference_types[inf_type] = []
        inference_types[inf_type].append(rel)
    
    return {
        "explicit": explicit,
        "inferred_agent": inferred_agent,
        "inferred_build": inferred_build,
        "by_attribute": by_attribute,
        "confidence_dist": confidence_dist,
        "inference_types": inference_types
    }

def print_report(data, analysis):
    """Pretty-print inference audit report."""
    total_relations = len(data.get("relations", []))
    explicit = len(analysis["explicit"])
    inferred_agent = len(analysis["inferred_agent"])
    inferred_build = len(analysis["inferred_build"])
    total_inferred = inferred_agent + inferred_build
    
    print("\n" + "="*70)
    print("INFERENCE QUALITY AUDIT")
    print("="*70 + "\n")
    
    # Summary statistics
    print(f"📊 SUMMARY")
    print(f"-" * 70)
    print(f"Total Relations:          {total_relations}")
    print(f"Explicit:                 {explicit} ({explicit*100//total_relations if total_relations else 0}%)")
    print(f"Agent-Inferred:           {inferred_agent} ({inferred_agent*100//total_relations if total_relations else 0}%)")
    print(f"Build-Inferred:           {inferred_build} ({inferred_build*100//total_relations if total_relations else 0}%)")
    print(f"Total Inferred:           {total_inferred} ({total_inferred*100//total_relations if total_relations else 0}%)")
    
    # By attribute type
    print(f"\n📋 BY RELATION TYPE")
    print(f"-" * 70)
    print(f"{'Type':<20} {'Explicit':>10} {'Agent':<10} {'Build':<10} {'Total':>10}")
    print("-" * 70)
    for attr in sorted(analysis["by_attribute"].keys()):
        breakdown = analysis["by_attribute"][attr]
        total = breakdown["explicit"] + breakdown["inferred_agent"] + breakdown["inferred_build"]
        print(f"{attr:<20} {breakdown['explicit']:>10} {breakdown['inferred_agent']:<10} {breakdown['inferred_build']:<10} {total:>10}")
    
    # By confidence level
    print(f"\n💪 INFERRED RELATIONS BY CONFIDENCE")
    print(f"-" * 70)
    total_conf = sum(analysis["confidence_dist"].values())
    for conf_level in ["high", "medium", "low", "unknown"]:
        count = analysis["confidence_dist"][conf_level]
        pct = (count * 100 // total_conf) if total_conf else 0
        print(f"{conf_level:<20} {count:>10} ({pct:>3}%)")
    
    # By inference type
    print(f"\n🔍 INFERRED RELATIONS BY TYPE")
    print(f"-" * 70)
    for inf_type in sorted(analysis["inference_types"].keys()):
        rels = analysis["inference_types"][inf_type]
        print(f"{inf_type:<40} {len(rels):>5}")
    
    # Suspicious inferences
    suspicious = [r for r in (analysis["inferred_agent"] + analysis["inferred_build"])
                  if r.get("inference_confidence") in ("low", "unknown")]
    
    if suspicious:
        print(f"\n⚠️  SUSPICIOUS INFERENCES (Low/Unknown Confidence)")
        print(f"-" * 70)
        for rel in suspicious[:10]:  # Show first 10
            print(f"\n  {rel.get('from')} → {rel.get('to')}")
            print(f"    Type:       {rel.get('attribute')}")
            print(f"    Confidence: {rel.get('inference_confidence', 'unknown')}")
            print(f"    Reason:     {rel.get('inference_reasoning', '(no reasoning provided)')[:60]}...")
        
        if len(suspicious) > 10:
            print(f"\n  ... and {len(suspicious) - 10} more")
    
    print("\n" + "="*70)
    print("END OF REPORT")
    print("="*70 + "\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 audit_inference.py /path/to/project")
        sys.exit(1)
    
    project_path = sys.argv[1]
    
    print(f"Loading docs_logical.json ...")
    data = load_docs_logical(project_path)
    print(f"✓ Loaded")
    
    print("Analyzing inferences...")
    analysis = analyze_inferences(data)
    print(f"✓ Analysis complete")
    
    print_report(data, analysis)

if __name__ == "__main__":
    main()
