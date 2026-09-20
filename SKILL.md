# 📚 NotaryMindAI — OCR GenAI + Paleographic Transcription of Historical Documents

**Project:** Multi-archive genealogical & notarial data extraction  
   "logical_documents": []
**Reusable:** Yes — generic for notarial archives, genealogy, administrative records, museums  
**Status:** Active development with multi-project support
**Language:** 🇬🇧 English (all code, documentation, and UI)

---

## 🎯 Objective

Convert photographs and PDFs of historical manuscripts into **structured, validated genealogical and property data** with:
- ✅ Reliable paleographic transcription (with uncertainty marks)
- ✅ Automatic entity extraction (persons, dates, places, values, properties)
- ✅ Clear segregation: verified data vs. structural template
- ✅ Policy: **Never invent** — leave empty if uncertain

> ⚠️ **OCR requires `github-copilot/claude-opus-4.8`**
> Weak models produce poor transcriptions. Always verify the active model before running OCR (`ocr` mode), 
> interpretation (`interpret` mode), or map generation (`map` mode). Register model used in `ocr_metadata.genai_model`.
>
> 🔤 **`projects/<project>/GLOSSARIO.md` (normalization rules) is applied at 2 moments:**
> 1. As **reading aid to GenAI** when generating image JSON/metadata 
> 2. In **normalization during build** (in-memory, never touching source files)

---

## 🏗️ Architecture Overview

### Structure: Project-Centric + Agnostic Tools

```
NotaryMindAi/
│
├── projects/
│   └── <project-name>/              ← PROJECT-SPECIFIC CONTENT
│       ├── imported/                 ← Raw images or documents (*.jpg, *.pdf)
│       ├── metadata/                 ← Per-image metadata (1 JSON per OCR image/PDF)
│       ├── docs_logical.json         ← Consolidated source of truth
│       └── docs_logical_map.json     ← Declarative document map (GenAI-generated)
│
├── skills/
│   └── transcript/                 ← AGNOSTIC TOOLS (work for any project)
│       ├── build_docs_logical.py    ← Build orchestrator (auto-detects project)
│       ├── find_new_docs.ts         ← Lists pending images
│       ├── validate_map.py          ← Validates project integrity
│       ├── SCHEMA.md                ← Data contract (immutable, v2.0)
│       └── SKILL.md                 ← Transcription workflow documentation
│
├── ui/                               ← VIEWER
│   ├── main.html                     ← Interactive graph viewer
│   └── SKILL.md                      ← Viewer features
│
└── README.md
```

### Key Design Principles

1. **Agnostic Build System**
   - Zero hardcoded data in scripts
   - Reads from: `docs_logical_map.json` + `metadata/*.json` + `GLOSSARIO.md`
   - Works for any project with auto-detection

2. **Immutable Source Files**
   - Image JSON files = OCR output, **never edited by hand**
   - Only modified via explicit GenAI reprocessing (`ocr` or `interpret`)
   - Guarantees data integrity

3. **Declarative Mapping**
   - All project-specific logic lives in **data files**, not code
   - `docs_logical_map.json` defines document structure
   - `metadata/*.json` contains per-image OCR
   - `GLOSSARIO.md` contains shared corrections

4. **Single Source of Truth**
   - `projects/<project>/docs_logical.json` = consolidated output
   - All analysis reads from this file (not original images)
   - Schema contract in `skills/transcript/SCHEMA.md`

---

## 📋 Processing Workflow

```
📷 projects/<project>/imported/ (JPG/PNG/PDF)   ← RAW IMAGES / DOCS
   ↓
🧠 GenAI with vision (claude-opus-4.8) reads each image  ←🔤 GLOSSARIO.md as reading aid
   ↓
📋 projects/<project>/metadata/<name>.json   ← OCR OUTPUT (1 JSON per image)
   ↓                                         (transcription + entities + properties + genealogy)
🗺️  projects/<project>/docs_logical_map.json  ← DECLARATIVE MAP
   ↓                                         (image→document grouping, title, type, continuations)
🔀 build_docs_logical.py consolidates by LOGICAL DOCUMENT  ←🔤 GLOSSARIO.md reapplied
   ↓                                         (agnostic, no embedded data; final in-memory normalization)
✅ projects/<project>/docs_logical.json      ← SOURCE OF TRUTH (schema in SCHEMA.md)
   ├─ genealogy block (aggregated, normalized)
   ├─ relations block (genealogy + transactions)
   └─ per-logical-doc: relations, transaction, sources, continuations
```

### Directory Roles

| Path | Purpose | Content |
| --- | --- | --- |
| `projects/<project>/imported/` | Raw documents | Images (`.jpg`, `.png`) or PDFs (`.pdf`) |
| `projects/<project>/metadata/` | Per-doc OCR output | JSON files (one per image/PDF) with transcription + entities |
| `projects/<project>/docs_logical_map.json` | Logical document mapping | Which images/PDFs form each document, titles, types |
| `projects/<project>/docs_logical.json` | Consolidated output | Read-only source of truth (auto-generated) |
| `projects/<project>/GLOSSARIO.md` | Normalization rules | Project-specific corrections + local knowledge |
| `skills/transcript/SCHEMA.md` | Data contract | Field definitions, validation, immutable specification |

---

## 🚀 Quick Start: Processing a Project

### 1. Create a New Project

```bash
mkdir -p projects/my-archive/{imported,metadata}

# Create map template
cat > projects/my-archive/docs_logical_map.json << 'EOF'
{
  "name": "My Archive Name",
  "description": "Description of the archive",
  "documents": []
}
EOF
```

### 2. Add Images and PDFs

```bash
cp /path/to/scans/*.jpg projects/my-archive/imported/
cp /path/to/pdfs/*.pdf projects/my-archive/imported/
```

### 3. List Pending Images

```bash
bun skills/transcript/find_new_docs.ts projects/my-archive
```

### 4. Generate OCR Metadata

For each image, use GenAI (claude-opus-4.8) to create `projects/my-archive/metadata/<doc-name>.json`.  
Use prompts from `skills/transcript/SKILL.md`.

### 5. Generate/Update Map

Update `projects/my-archive/docs_logical_map.json` with document groupings.

### 6. Build Consolidated Output

```bash
python3 skills/transcript/build_docs_logical.py projects/my-archive
```

### 7. Validate

```bash
python3 skills/transcript/validate_map.py projects/my-archive
```

### 8. View Results

```bash
python3 -m http.server 8000
# Open: http://localhost:8000/ui/main.html?project=my-archive
```

---

## 🔧 Tool Reference

### build_docs_logical.py

**Location:** `skills/transcript/build_docs_logical.py`

Consolidates project data into source-of-truth JSON.

**Usage:**
```bash
# From project directory
cd projects/my-archive
python3 ../../skills/transcript/build_docs_logical.py .

# From workspace
python3 skills/transcript/build_docs_logical.py projects/my-archive
```

**Features:**
- ✅ Auto-detects project path
- ✅ Applies GLOSSARIO normalization
- ✅ Validates schema compliance
- ✅ Aggregates relations by logical document

---

### find_new_docs.ts

**Location:** `skills/transcript/find_new_docs.ts`

Lists images in `imported/` that lack corresponding `metadata/` JSON.

**Usage:**
```bash
bun skills/transcript/find_new_docs.ts projects/my-archive
```

**Output:**
```
image1.jpg
image2.jpg
Project: /workspace/NotaryMindAi/projects/my-archive
Imported: 10 | Transcribed: 8 | PENDING: 2
```

---

### validate_map.py

**Location:** `skills/transcript/validate_map.py`

Validates project map integrity (no duplicate vendors, consistent roles, etc.).

**Usage:**
```bash
python3 skills/transcript/validate_map.py projects/my-archive
```

**Output:**
```
✅ No errors detected
📊 Summary: 0 problem(s)
```

---

### main.html

**Location:** `ui/main.html`

Interactive relationship and property graph viewer.

**Usage:**
```
http://localhost:8000/ui/main.html?project=my-archive
```

**Features:**
- ✅ Dynamic project selection
- ✅ Genealogy graph with Sugiyama layout
- ✅ Property visualization
- ✅ Relationship filtering
- ✅ Image drilldown

---

## 📖 Processing Modes (Detailed)

### OCR / Interpret: Create or Reprocess Image JSON via GenAI

Image JSON only changes **on explicit request**, via GenAI, always using the **same schema**.

**`ocr` — Visual OCR of photo** (for new images or complete retranscription)
- Reads the image and creates/reproduces the image JSON
- Fields: `full_transcript` + `entities` + `properties` + `genealogy` + `ocr_metadata`
- ⭐ **Critical:** When extracting `genealogy`, also capture **transactional relationships per individual**:
  - Each seller/debtor and buyer/creditor as `persons[]` (with explicit role)
  - One relationship **per individual** in `relations[]` (e.g., `sells to`, with `category` and `value`)

**`interpret` — Interpretation of `full_transcript`** (without rereading photo)
- GenAI reads the already-transcribed text and with GLOSSARIO.md support
- Derives (or re-derives) `entities`, `properties`, `genealogy`
- Including transactional relationships per person (same `ocr` requirement)

**Typical workflow for new images:**
```bash
# 1. List pending images
bun skills/transcript/find_new_docs.ts projects/my-archive

# 2. Ask before proceeding
# (Always ask user, show plan, wait for confirmation)

# 3. Run OCR (`ocr` mode) on new images only
# Use GenAI with GLOSSARIO.md as reading aid
# Save to projects/my-archive/metadata/<name>.json

# 4. Update map
# Edit projects/my-archive/docs_logical_map.json
# Define document groupings, titles, types, continuations

# 5. Regenerate
python3 skills/transcript/build_docs_logical.py projects/my-archive

# 6. Validate
python3 skills/transcript/validate_map.py projects/my-archive
```

---

### Glossary Updates (No Re-OCR)

Edit `projects/<project>/GLOSSARIO.md` without modifying image JSON.

**Two types of entries:**

1. **Reading Corrections** (`**Canonical** - NOT "Wrong"`)
   - Substitution rules for transcription errors
   - Applied in-memory during build
   - Contradictory rules are discarded to preserve intentional variants

2. **Local Knowledge** (```json``` block: `identities`, `persons`, `relations`)
   - Facts not in transcriptions (e.g., children of X, aliases)
   - First name in `identities` = canonical
   - Applied with `source:"glossary"` marker

**Workflow:**
```bash
# 1. Edit GLOSSARIO.md
# Add corrections or local knowledge

# 2. Regenerate (no re-OCR)
python3 skills/transcript/build_docs_logical.py projects/my-archive

# 3. Validate
python3 skills/transcript/validate_map.py projects/my-archive
```

---

### `map`: Generate/Update Logical Document Map

Create or update `docs_logical_map.json` **without** touching image JSON.

**Workflow:**
```bash
# 1. GenAI reads full_transcript fields
# 2. With GLOSSARIO.md as reading aid, deduces:
#    - Document grouping (images → logical documents)
#    - Titles
#    - Types
#    - Continuations
#    - Transaction info (buyer/seller/value)

# 2. GenAI writes docs_logical_map.json
# Following SCHEMA.md contract exactly

# 3. Regenerate
python3 skills/transcript/build_docs_logical.py projects/my-archive
```

---

## 📋 Critical Practices

### Transcription
```
✓ Mark uncertainties: "A[ntonio?] Vieira"
✓ Mark illegibility: "[illegible — lines 3–5]"
✓ Preserve old spelling (e.g., "senhor" vs "sr.")
✓ Maintain formatting (paragraphs, alignment)
✗ NEVER invent: leave empty if you can't read
```

### Entities
```
✓ Extract everything readable with ~80%+ confidence
✓ Mark doubts: ["Person [?]"]
✓ Values: preserve original format (réis, escudos, etc.)
✓ Dates: consistent format (DD of Month of YYYY)
✗ NEVER infer: if not explicit, leave empty
```

### Properties
```
✓ Description: type of property as written
✓ Confrontations: ONLY what's written
✓ If no neighbor mentioned: [illegible] or empty
✓ Values/articles: empty if not stated
✗ NEVER infer relationships between documents
```

### OCR Confidence Levels
```
very_low:    < 40%   (very cursive, damaged document)
low:         40-60%  (some legible sections, others not)
medium:      60-75%  (mostly legible, some doubts)
high:        75-90%  (legible, few uncertainties [?])
very_high:   > 90%   (nearly perfect, no uncertainties)
```

---

## ✅ Quality Checklist

Before delivering:

- [ ] All documents with data have `ocr_confidence` filled
- [ ] No "invented" data (always verifiable or empty)
- [ ] Uncertainties marked with [?], illegibility with [illegible]
- [ ] Confrontations are ONLY what's in the document
- [ ] Values and articles in original format
- [ ] Dates in consistent format
- [ ] Names preserve historical variants
- [ ] JSON valid (test with `jq empty`)
- [ ] Clear segregation: real data vs. structure

---

## 🔐 Non-Negotiable Rules

1. **`docs_logical.json` is the source of truth**
   - Always follows current SCHEMA.md
   - Immutable once generated (modify via regeneration only)

2. **`metadata/*.json` are OCR output, never hand-edited**
   - Only changes via explicit GenAI reprocessing (`ocr`/`interpret`)
   - Always same schema

3. **Build is agnostic**
   - Zero embedded data in scripts
   - Reads from: map + metadata + GLOSSARIO.md

4. **Normalization is in-memory**
   - GLOSSARIO.md never modifies source files
   - Only applied during build

5. **Always ask before altering existing data**
   - Show plan, wait for confirmation
   - Never surprise users with changes

---

## 🌍 Adaptation to Other Contexts

### Genealogy (births, marriages, deaths)
- `genealogy` field: focused on dates and filiations
- Prompts: ancestry chains, date extraction

### Notariat (deeds, wills, donations)
- Add field: `"type_legal_act": "sale | inheritance | donation | ..."`
- Prompts: transaction details, conditions

### Administration (official records)
- Add field: `"issuing_entity": "City Council | ..."`
- Prompts: decisions and effective dates

### Museums/Archives (heritage preservation)
- Add field: `"conservation_status": "good | damaged | ..."`
- Prompts: material description

---

## 🎓 GenAI Prompts

See `skills/transcript/SKILL.md` for ready-to-use prompts:
- **Prompt 1:** Basic paleographic transcription
- **Prompt 2:** Entity extraction
- **Prompt 3:** Combined transcription + entities

All prompts include `GLOSSARIO.md` as context.

---

## 📚 Complete Documentation

| File | Purpose |
|------|---------|
| **README.md** | Project overview |
| **SKILL.md** | Processing workflows and modes |
| **skills/transcript/GLOSSARY-TEMPLATE.md** | Source template for each new project's build/OCR-compatible glossary |
| **skills/transcript/GENDER-RULES-TEMPLATE.json** | Source template for gender inference keywords (Portuguese + English) |
| **skills/transcript/SCHEMA.md** | Immutable data contract |
| **projects/<project>/GLOSSARIO.md** | Normalization rules (edit freely) |
| **projects/<project>/gender_rules.json** | Project-specific gender inference keywords |
| **ui/SKILL.md** | Viewer features |
| **api/README.md** | Current REST endpoints and runtime configuration |

---

## 🔄 Typical Session Workflow

The UI exposes the same workflow through Settings: Project (load/new/external/delete),
Import Files, Build Metadata (`ocr`/`interpret`/`build`/`map` plus glossary editor), and Project Chat. All
project-aware controls default to the project currently loaded in the viewer.

1. **Preparation**
   ```bash
   cd NotaryMindAi
   bun skills/transcript/find_new_docs.ts projects/cotimos
   ```

2. **Process Images**
   - Ask user for confirmation
   - Run GenAI `ocr` or `interpret`
   - Save metadata JSON files

3. **Update Map**
   - Edit `projects/cotimos/docs_logical_map.json`
   - Define document groups, titles, types

4. **Regenerate**
   ```bash
   python3 skills/transcript/build_docs_logical.py projects/cotimos
   ```

5. **Validate**
   ```bash
   python3 skills/transcript/validate_map.py projects/cotimos
   python3 skills/transcript/validate_docs.py projects/cotimos
   ```

6. **Report**
   ```
   ✅ Build: 23 DL, 59 images, 71 relations
   ✅ Validation: 0 errors
   ✅ Pending: 0 images
   ```

---

## 📞 Support

### Common Issues

**"Pending images found"**
→ Run GenAI `ocr` on those images, save to `metadata/`

**"Validation error: duplicate vendors"**
→ Check `docs_logical_map.json` for transactional data

**"JSON invalid"**
→ Run `jq empty docs_logical.json` to identify syntax error

**"Viewer not loading images"**
→ Check URL parameter: `?project=my-archive`

### Resources

- `skills/transcript/SCHEMA.md` — Full data contract
- `projects/<project>/GLOSSARIO.md` — Current normalization rules
- `README.md` — Architecture and design decisions

---

## 📄 License

Freely reusable for historical, genealogical, administrative, and archival projects.

**Last updated:** 2026-09-13  
**Version:** 2.0 (Project-centric architecture with multi-archive support, English localization complete)
