#!/usr/bin/env python3
"""Builds docs_logical.json (SINGLE SOURCE OF TRUTH FOR PROCESSED DATA) from raw sources.

Principles (see skills/transcript/SCHEMA.md):
- SCHEMA-AGNOSTIC: this script does NOT contain document data. Always reads from sources:
    1) projects/<project>/docs_logical_map.json  (declarative map: image→logical document
       grouping, title, type, transaction)
    2) projects/<project>/metadata/*.json               (GenAI OCR per document (image or PDF))
    3) projects/<project>/GLOSSARIO.md                 (reading normalization, project-specific)
- Normalizes relations BY LOGICAL DOCUMENT (not by image): aggregates and deduplicates,
  maintaining links to original images/documents as metadata (`sources`, `source_images`).
- NEW v2.0: Top-level persons[] and relations[] only (no genealogy wrapper).
  Inference marking (inferedbyai/infered), variant grouping with confidence/reasoning,
  transaction attributes on relations.
- If GLOSSARIO changes, just reprocess (run this script) — no embedded data.
- Additive schema: see SCHEMA.md. Do NOT remove/rename fields.
"""
import json, os, sys, datetime, re, unicodedata

SCHEMA_VERSION = "2.0"
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

def infer_gender(person, relations_text, gender_rules):
    """Infer gender from relations text using keywords from gender_rules.
    Returns (gender, source) where source is 'explicit' or 'inferred'.
    Prioritizes person's OWN roles (outgoing relations) over others' roles (incoming).
    """
    if person.get('gender'):
        return (person['gender'], 'explicit')
    
    if not gender_rules or 'keywords' not in gender_rules:
        return (None, None)
    
    text_norm = relations_text.lower()
    f_keywords = gender_rules.get('keywords', {}).get('female', [])
    m_keywords = gender_rules.get('keywords', {}).get('male', [])
    
    # Match female keywords
    if f_keywords:
        pattern = r'\b(' + '|'.join(re.escape(k) for k in f_keywords) + r')\b'
        if re.search(pattern, text_norm):
            return ('F', 'context')
    
    # Match male keywords
    if m_keywords:
        pattern = r'\b(' + '|'.join(re.escape(k) for k in m_keywords) + r')\b'
        if re.search(pattern, text_norm):
            return ('M', 'context')
    
    return (None, None)

def enrich_persons_with_gender(persons, relations, project_path):
    """Add gender_source field to track whether gender is explicit or inferred.
    Prioritizes person's own role (where they are 'from') over their relatives' roles.
    """
    # Load gender rules from project
    gender_rules = None
    rules_path = os.path.join(project_path, 'gender_rules.json')
    if os.path.exists(rules_path):
        try:
            with open(rules_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                gender_rules = config.get('gender_inference', {})
        except:
            pass
    
    # Build relation map: person_name → [relations]
    # Distinguish between 'from' (subject/own role) and 'to' (object/relative's role)
    rels_by_person_from = {}  # Person's own roles
    rels_by_person_to = {}    # Person as object (others' roles)
    
    for r in relations:
        from_name = r.get('from', '')
        to_name = r.get('to', '')
        rel_text = r.get('relation', '')
        
        if from_name:
            if from_name not in rels_by_person_from:
                rels_by_person_from[from_name] = []
            rels_by_person_from[from_name].append(rel_text)
        
        if to_name:
            if to_name not in rels_by_person_to:
                rels_by_person_to[to_name] = []
            rels_by_person_to[to_name].append(rel_text)
    
    # Enrich persons with gender_source
    for p in persons:
        if p.get('gender'):
            p['gender_source'] = 'explicit'
        else:
            # Try to infer gender: prioritize own roles over others' roles
            name = p.get('name', '')
            
            # First try: person's own roles (where they are the subject)
            rels_text_from = ' '.join(rels_by_person_from.get(name, []))
            gender, source = infer_gender(p, rels_text_from, gender_rules)
            
            # If no match, fall back to: person as object (others' roles)
            if not gender:
                rels_text_to = ' '.join(rels_by_person_to.get(name, []))
                gender, source = infer_gender(p, rels_text_to, gender_rules)
            
            if gender:
                p['gender'] = gender
                p['gender_source'] = source
    
    return persons

def setup_paths(project_path):
    """Setup paths based on project location."""
    if not os.path.isdir(project_path):
        raise ValueError(f"Project path does not exist: {project_path}")
    return {
        "project": project_path,
        "metadata": os.path.join(project_path, "metadata"),
        "map": os.path.join(project_path, "docs_logical_map.json"),
        "glossary": os.path.join(project_path, "GLOSSARIO.md"),
        "output": os.path.join(project_path, "docs_logical.json"),
    }

# Auto-detect project path if not provided
if len(sys.argv) > 1:
    PROJECT_PATH = sys.argv[1]
else:
    # Try to find project by looking for docs_logical_map.json up the directory tree
    cwd = os.getcwd()
    PROJECT_PATH = None
    for attempt in [cwd, os.path.dirname(cwd), os.path.dirname(os.path.dirname(cwd))]:
        map_file = os.path.join(attempt, "docs_logical_map.json")
        if os.path.exists(map_file):
            PROJECT_PATH = attempt
            break
    if not PROJECT_PATH:
        print("Usage: python3 build_docs_logical.py [/path/to/project]", file=sys.stderr)
        print("Or run from within a project directory with docs_logical_map.json", file=sys.stderr)
        sys.exit(1)

PATHS = setup_paths(PROJECT_PATH)

# Normalize project name for use in relative paths
project_name = os.path.basename(os.path.abspath(PROJECT_PATH))

IMG_DIR = PATHS["metadata"]
MAP_PATH = PATHS["map"]
GLOSS_PATH = PATHS["glossary"]
OUT_PATH = PATHS["output"]

# ---------------------------------------------------------------- glossary
def load_glossario(path):
    """Extracts pairs (wrong -> canonical) from GLOSSARIO.md, content-agnostic.
    Recognizes lines like:  - **Canonical** — NOT "Wrong"/"Wrong2".
    and                          Always correct "Wrong" → "Canonical"."""
    subs = []
    if not os.path.exists(path):
        return subs
    txt = open(path, encoding="utf-8").read()
    for m in re.finditer(r"\*\*(.+?)\*\*.*?N[ÃA]O\s+(.+)", txt):
        canon = m.group(1).strip()
        for wrong in re.findall(r'"([^"]+)"', m.group(2)):
            if wrong and wrong.lower() != canon.lower():
                subs.append((wrong, canon))
    for m in re.finditer(r'[Cc]orrect\s+always\s+"([^"]+)"\s*[→-]+>?\s+"?([^"\.]+)"?', txt):
        subs.append((m.group(1).strip(), m.group(2).strip()))
    # Preserve discrepancies: discard conflicting rules (a term that is
    # simultaneously 'wrong' in one rule and 'canonical' in another, or mutual substring).
    # Ex.: Rolinda↔Arlinda — variants are kept, not uniformized.
    canons = [c for _, c in subs]
    def _conflict(w):
        wl = w.lower()
        for c in canons:
            cl = c.lower()
            if wl == cl or wl in cl or cl in wl:
                return True
        return False
    subs = [(w, c) for (w, c) in subs if not _conflict(w)]
    # Sort by length descending (apply more specific terms first)
    subs.sort(key=lambda p: -len(p[0]))
    # Deduplicate while preserving order
    seen, uniq = set(), []
    for w, c in subs:
        if (w, c) not in seen:
            seen.add((w, c)); uniq.append((w, c))
    return uniq


def apply_gloss(s, subs):
    if not isinstance(s, str) or not s:
        return s
    for wrong, canon in subs:
        s = re.sub(r"\b" + re.escape(wrong) + r"\b", canon, s)
    return s

def gloss_deep(obj, subs):
    if isinstance(obj, str):
        return apply_gloss(obj, subs)
    if isinstance(obj, list):
        return [gloss_deep(x, subs) for x in obj]
    if isinstance(obj, dict):
        return {k: gloss_deep(v, subs) for k, v in obj.items()}
    return obj

# ---------------------------------------------------------------- utilities
ALIAS = {}   # norm(variant) -> canonical name (from GLOSSARIO `identities`)
def _canon(name):
    return ALIAS.get(_norm(name), name)

def load_glossario_genealogy(path):
    """Reads the first ```json``` block from GLOSSARIO.md with persons/relations/identities
    (local knowledge). Deterministic; no NLP. Returns dict with the 3 keys."""
    empty = {"identities": [], "persons": [], "relations": []}
    if not os.path.exists(path):
        return empty
    txt = open(path, encoding="utf-8").read()
    for b in re.findall(r"```json\s*(.*?)```", txt, re.S):
        try:
            obj = json.loads(b)
        except Exception:
            continue
        if isinstance(obj, dict) and any(k in obj for k in ("relations", "persons", "identities")):
            for k in empty:
                obj.setdefault(k, [])
            return obj
    return empty

def supersede(rels):
    """Remove `descent` (typically inferred) when there is an explicit/glossary `filiation`
    for the same pair (from→to)."""
    fil = {(_norm(r["from"]), _norm(r["to"])) for r in rels if r.get("attribute") == "filiation"}
    return [r for r in rels
            if not (r.get("attribute") == "descent" and (_norm(r["from"]), _norm(r["to"])) in fil)]

def _norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()

def _clean(s):
    """Remove parentheses/brackets to compare person names in transactions."""
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", str(s or ""))).strip()

def _rel_cat(rel):
    """Detect relation category from text (DEPRECATED: use 'attribute' field instead).
    
    This function is language-dependent and only used as fallback.
    Agents should extract relations with 'attribute' field containing
    the English relation type (filiation, marriage, sale, etc.).
    See SCHEMA.md for language-agnostic rule definitions.
    """
    r = (rel or "").lower()
    if re.search(r"descend", r): return "descent"
    if re.search(r"filh", r): return "filiation"
    if re.search(r"cas(ad|ou|amento)|cônjuge|conjuge|marido|esposa|mulher de|divorc|vi[uú]v|separad|ex-mulher|ex-marido|ex-esposa", r): return "marriage"
    if re.search(r"irm", r): return "kinship"
    if re.search(r"genro|nora|sogr|cunhad|afin", r): return "affinity"
    if re.search(r"padrinho|madrinha", r): return "godparent"
    if re.search(r"herdeir|herança|heranca|legítim|legitim|coherdeir", r): return "inheritance"
    return "other"

SYM = ("marriage", "kinship")  # symmetric categories (A-B == B-A)
_PERSON_FIELDS = ["birth", "baptism", "death", "roles", "profession", "birthplace", "residence", "notes", "gender", "alias", "burial"]

def merge_persons(contribs):
    """Merge persons from multiple documents.
    
    contribs: list of (img, person_dict)
    - persons[].roles is now an array (person can have multiple roles)
    - persons[].variants is array with {name, source, confidence, reasoning}
    """
    by = {}
    for img, p in contribs:
        name = p.get("name")
        if not name: continue
        cn = _canon(name)
        k = _norm(cn)
        e = by.setdefault(k, {"name": cn, "variants": [], "roles": [], "_notes": [], "source_images": []})
        
        # Merge roles (array)
        for role in (p.get("roles") or []):
            if role and role not in e["roles"]:
                e["roles"].append(role)
        
        # Add name as variant if different from canonical
        if name != cn:
            variant_entry = {"name": name}
            # Don't duplicate identical variant entries
            if not any(v.get("name") == name for v in e["variants"]):
                e["variants"].append(variant_entry)
        
        # Merge other person fields
        for f in _PERSON_FIELDS:
            if f == "roles": continue  # already handled
            if p.get(f) and not e.get(f): 
                e[f] = p[f]
        
        # Merge variants with metadata
        for v in (p.get("variants") or []):
            if isinstance(v, dict):
                # Variant has metadata (source, confidence, reasoning)
                existing = next((ev for ev in e["variants"] if ev.get("name") == v.get("name")), None)
                if not existing:
                    e["variants"].append(v)
            else:
                # Legacy: variant is just a string
                if v and not any(ev.get("name") == v for ev in e["variants"]):
                    e["variants"].append({"name": v})
        
        if p.get("notes") and p["notes"] not in e["_notes"]: 
            e["_notes"].append(p["notes"])
        if img not in e["source_images"]: 
            e["source_images"].append(img)
    
    out = []
    for e in by.values():
        # Remove variants that are just the canonical name
        e["variants"] = [v for v in e["variants"] if _norm(v.get("name") if isinstance(v, dict) else v) != _norm(e["name"])]
        if not e["variants"]: 
            e.pop("variants")
        
        # Remove empty roles
        if not e["roles"]:
            e.pop("roles")
        
        notes = e.pop("_notes")
        if notes: 
            e["notes"] = " | ".join(notes)
        out.append(e)
    return out

SOURCE_RANK = {"explicit": 2, "explicito": 2, "glossary": 1, "inferred": 0}

def merge_relations(contribs):
    """contribs: list of (img, relation_dict). Deduplicates by (from, attribute, to).
    Precedence of `source`: explicit > glossary > inferred.
    Relation resolution order:
    1. Check 'attribute' field (English relation type from agent extraction)
    2. Check 'category' field (pre-classified, legacy)
    3. Fall back to _rel_cat() parsing (language-dependent, deprecated)
    NEW v2.0: Preserves inference fields and transaction attributes.
    """
    by = {}
    for img, r in contribs:
        from_p, to_p = r.get("from"), r.get("to")
        if not from_p or not to_p: continue
        from_p, to_p = _canon(from_p), _canon(to_p)
        attr = r.get("attribute") or r.get("category") or _rel_cat(r.get("relation") or r.get("type"))
        a, b = _norm(from_p), _norm(to_p)
        if attr in SYM and a > b:
            from_p, to_p, a, b = to_p, from_p, b, a
        key = (a, attr, b)
        e = by.get(key)
        if e is None:
            e = {"from": from_p, "relation": r.get("relation") or r.get("type") or attr, "to": to_p,
                 "attribute": attr, "source_images": []}
            # Only add source if not default (inferred)
            source = r.get("source", "inferred")
            if source != "inferred":
                e["source"] = source
            # Only add inference fields if agent involved
            if r.get("inferedbyai"):
                e["inferedbyai"] = True
                e["inference_type"] = r.get("inference_type", "inferred_same_doc")
                e["inference_confidence"] = r.get("inference_confidence", "medium")
                if r.get("inference_reasoning"): e["inference_reasoning"] = r["inference_reasoning"]
            for extra in ("property", "seller", "buyer", "mortgagor", "mortgagee", "debtor", "creditor",
                         "value", "date", "date_precision", "date_original", "label", "notes", "observ", "location", "status"):
                if r.get(extra): e[extra] = r[extra]
            by[key] = e
        else:
            nf = r.get("source", "inferred")
            # Update source only if it ranks higher
            if SOURCE_RANK.get(nf, 1) > SOURCE_RANK.get(e.get("source", "inferred"), 1):
                e["source"] = nf
                e["relation"] = r.get("relation") or e["relation"]
        if img not in e["source_images"]: e["source_images"].append(img)
    return list(by.values())

def merge_list(acc, items):
    for it in items:
        if it not in acc: acc.append(it)

CONF_RANK = {"very_low": 0, "low": 1, "medium": 2, "high": 3, "very_high": 4}
CONF_INV = {v: k for k, v in CONF_RANK.items()}

def load_img(doc_name):
    # Load metadata JSON for document (image or PDF)
    # doc_name can be: page_001.jpg, page_001.pdf, etc.
    # Metadata always in: metadata/<basename>.json (without extension)
    import os.path
    base_name = os.path.splitext(doc_name)[0]
    json_path = os.path.join(IMG_DIR, base_name + ".json")
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------------- build
def build():
    subs = load_glossario(GLOSS_PATH)
    gg = load_glossario_genealogy(GLOSS_PATH)
    gg = gloss_deep(gg, subs)
    ALIAS.clear()
    for grp in gg.get("identities", []):
        if isinstance(grp, list) and len(grp) >= 2:
            canon = grp[0]
            for alias in grp[1:]:
                ALIAS[_norm(alias)] = canon
    mp = json.load(open(MAP_PATH, encoding="utf-8"))
    ARCHIVE_NAME = mp.get("name") or mp.get("project") or project_name
    ARCHIVE_DESC = mp.get("description", "Genealogical and notarial archive")
    DOCS = mp.get("logical_documents")
    if not isinstance(DOCS, list):
        raise ValueError(
            f"{MAP_PATH} must contain a 'logical_documents' array "
            "(see skills/transcript/SCHEMA.md)"
        )

    docs_out = []
    gen_all_p, gen_all_r = [], []   # global genealogy contributions
    rel_all = []                    # all relations (any type), with origin DL

    for d in DOCS:
        imgs = d["images"]
        ents = {"names": [], "dates": [], "places": [], "values": []}
        props, sources, trans_parts, obs_parts = [], [], [], []
        img_txs = []                     # transactions declared at image level (`reinterpret`)
        confs, statuses, document_dates, locs = [], [], [], []
        model = None
        gen_p, gen_r = [], []
        for img in imgs:
            j = gloss_deep(load_img(img), subs)   # applies GLOSSARIO to source
            model = j.get("ocr_metadata", {}).get("genai_model", model)
            _itx = j.get("transaction")
            if _itx: img_txs.append((img, _itx))
            for k in ents: merge_list(ents[k], j.get("entities", {}).get(k, []))
            for pr in j.get("properties", []):
                pr = dict(pr); pr["_source"] = img
                props.append(pr)
            # NEW v2.0: Top-level persons/relations only (no genealogy wrapper)
            persons_data = j.get("persons", [])
            relations_data = j.get("relations", [])
            for p in persons_data:
                gen_p.append((img, p)); gen_all_p.append((img, p))
            for r in relations_data:
                gen_r.append((img, r)); gen_all_r.append((img, r))
            m = j.get("ocr_metadata", {})
            est = m.get("status", "?"); cf = m.get("ocr_confidence", "?")
            statuses.append(est)
            if cf in CONF_RANK: confs.append(CONF_RANK[cf])
            sources.append({"image": img,
                           "json_file": f"metadata/{os.path.splitext(img)[0]}.json",
                           "status": est, "ocr_confidence": cf})
            trans_parts.append(f"===== [{img}] =====\n{j.get('full_transcript', '')}")
            if m.get("notes"): obs_parts.append(f"[{img}] {m['notes']}")
            if j.get("document_date") and j["document_date"] not in document_dates:
                document_dates.append(j["document_date"])
            if j.get("location") and j["location"] not in locs:
                locs.append(j["location"])

        conf_global = CONF_INV[round(sum(confs) / len(confs))] if confs else "?"
        status_global = ("complete" if all(e == "complete" for e in statuses)
                         else ("partial" if {"complete", "partial"} & set(statuses) else "?"))
        doc_gen_persons = merge_persons(gen_p)
        doc_gen_relations = merge_relations(gen_r)

        # Extract transactions from economic/inheritance relations
        # Transactions are special relations with attributes in [sale, purchase, mortgage, debt, inheritance]
        doc_rel = list(doc_gen_relations)
        
        # Try to extract transaction from first economic/inheritance relation
        tx = None
        _transaction_attrs = {"sale", "purchase", "mortgage", "debt", "inheritance", "heir"}
        for rel in doc_gen_relations:
            if rel.get("attribute") in _transaction_attrs:
                # Extract transaction structure from relation
                tx = {
                    "nature": rel.get("attribute"),
                    "seller": rel.get("seller") or rel.get("from"),
                    "buyer": rel.get("buyer") or rel.get("to"),
                    "heir": rel.get("heir"),
                    "from": rel.get("from"),
                    "value": rel.get("value"),
                    "property": rel.get("property"),
                    "label": rel.get("label"),
                }
                break
        for r in doc_rel:
            rel_all.append((d["id"], r))

        doc_obj = {
            "id": d["id"],
            "title": apply_gloss(d["title"], subs),
            "document_type": apply_gloss(d["type"], subs),
            "document_date": document_dates,
            "location": locs,
            "n_images": len(imgs),
            "sources": sources,                 # links to original documents/images (metadata)
            "entities": ents,
            "persons": doc_gen_persons,        # persons of this logical document
            "properties": props,
            "relations": doc_rel,              # relations of this logical document
            "full_transcript": "\n\n".join(trans_parts),
            "ocr_metadata": {
                "genai_model": model,
                "method": "genuine visual reading (paleographic) per image, consolidated by logical document",
                "global_ocr_confidence": conf_global,
                "status": status_global,
                "notes": " | ".join(obs_parts),
            },
        }
        if tx:
            tx = dict(tx)
            if tx.get("buyer"): tx["buyer"] = _canon(tx["buyer"])
            if tx.get("seller"): tx["seller"] = _canon(tx["seller"])
            doc_obj["transaction"] = tx
        docs_out.append(doc_obj)

    # ---- Contributions from GLOSSARIO (local knowledge), source="glossary" ----
    for p in gg.get("persons", []):
        gen_all_p.append(("GLOSSARIO", p))
    for r in gg.get("relations", []):
        r = dict(r); r.setdefault("source", "glossary")
        gen_all_r.append(("GLOSSARIO", r))
        rel_all.append(("GLOSSARIO", r))

    # Aggregate all persons and relations (top-level)
    persons_top = merge_persons(gen_all_p)
    relations_top = supersede(merge_relations(gen_all_r))

    # Add gender_source tracking to persons
    persons_top = enrich_persons_with_gender(persons_top, relations_top, PROJECT_PATH)

    out = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "skills/transcript/SKILL.md",
        "model": "github-copilot/claude-opus-4.8",
        "method": "genuine_visual_reading",
        "name": ARCHIVE_NAME,
        "description": ARCHIVE_DESC,
        "glossary": "projects/{}/GLOSSARIO.md".format(project_name),
        "map": "projects/{}/docs_logical_map.json".format(project_name),
        "structure": {
            "imported": "projects/<project>/imported/(*.jpg, *.jpeg, *.png, *.pdf)",
            "metadata_ocr": "projects/{}/metadata/*.json".format(project_name),
            "map_logicals": "projects/{}/docs_logical_map.json".format(project_name),
            "consolidated": "projects/{}/docs_logical.json".format(project_name),
            "persons": "top-level `persons` array (aggregate, normalized by GLOSSARIO)",
            "relations": "top-level `relations` array (aggregate of all relations: genealogy + economic + legal + succession)",
        },
        "total_logical_documents": len(docs_out),
        "total_images": sum(x["n_images"] for x in docs_out),
        "persons": persons_top,
        "relations": relations_top,
        "documents": docs_out,
    }
    json.dump(out, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"OK schema {SCHEMA_VERSION}: {len(docs_out)} DL, {out['total_images']} images | "
          f"persons={len(persons_top)}, relations={len(relations_top)} | glossary={len(subs)} rules")

if __name__ == "__main__":
    build()
