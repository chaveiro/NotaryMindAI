# NotaryMindAi v2.0 Schema

## Overview

NotaryMindAi uses a **v2.0 data model** with top-level `persons` and `relations` arrays in `docs_logical.json`. All data is **language-agnostic** and sourced from project configuration files.

---

## Person Object

```json
{
  "name": "Francisco Sebastião Álvaro",
  "gender": "M",
  "gender_source": "explicit",
  "variants": [
    {"name": "Fr. Sebastião Álvaro", "source": "documents"}
  ],
  "birth": "c. 1700",
  "death": "1780",
  "birthplace": "Cótimos",
  "roles": ["landowner", "witness"],
  "source_images": ["20260827_230534.jpg"],
  "notes": "Married Arlinda Maria"
}
```

### Fields

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `name` | string | metadata | Canonical person name (from GLOSSARIO identities) |
| `gender` | string | metadata/build | Gender: `"F"` or `"M"` |
| `gender_source` | string | build | Source of gender: `"explicit"` (metadata) or `"inferred"` (relations keywords) |
| `variants` | array | metadata | Alternative name readings with confidence/source |
| `birth` | string | metadata | Birth date or date estimate |
| `death` | string | metadata | Death date or date estimate |
| `baptism` | string | metadata | Baptism date |
| `birthplace` | string | metadata | Location of birth |
| `roles` | array | metadata | Occupations/social roles |
| `source_images` | array | metadata | Images where person appears |
| `notes` | string | metadata | Free-text observations |

### Gender Field & Inference

The `gender_source` field indicates how the gender value was determined:

- **`"explicit"`** — Person has explicit `gender` field in GLOSSARIO/metadata
- **`"inferred"`** — Gender determined from genealogical relations (e.g., "filha de" → Female, "filho de" → Male)

#### How Inference Works

1. **Build reads:** `gender_rules.json` from project directory
2. **Scans relations:** For each person without explicit gender, collects relation keywords
3. **Matches patterns:** Portuguese role words (filha, mãe, filho, pai, etc.)
4. **Outputs:** `person.gender` + `person.gender_source: "inferred"`
5. **UI displays:** Gender with "(inferred)" label for transparency

**Example:**  
If "Justina de Jesus" has no explicit gender but relations include "filha de Luiz", the build infers `gender: "F"` with `gender_source: "inferred"`.

---

## Relation Object

```json
{
  "from": "Arlinda Maria",
  "to": "Luiz do Nascimento Dias",
  "relation": "filha de",
  "attribute": "filiation",
  "source": "glossary",
  "source_images": ["20260827_231046.jpg"],
  "status": "documented",
  "date": "1750-1770",
  "location": "Cótimos",
  "notes": "Confirmed via marriage record"
}
```

### Fields

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `from` | string | metadata | Source person name |
| `to` | string | metadata | Target person name |
| `relation` | string | metadata | Portuguese relation label (e.g., "filha de", "vendeu a") |
| `attribute` | string | metadata | Canonical relation type: `filiation`, `marriage`, `kinship`, `sale`, `inheritance`, etc. |
| `source` | string | build | Origin: `"glossary"`, `"transcribed"`, `"inferred"` |
| `source_images` | array | metadata | Images documenting relation |
| `status` | string | metadata | Confidence: `documented`, `probable`, `inferred` |
| `date` | string | metadata | Date of relation occurrence |
| `location` | string | metadata | Location context |
| `inference_type` | string | metadata | Type of inference (if applicable) |
| `inference_confidence` | string | metadata | Confidence level: `high`, `medium`, `low` |

---

## Project Configuration

### `gender_rules.json` (per-project)

Controls gender inference for persons without explicit gender. Located in project root: `projects/{project}/gender_rules.json`

```json
{
  "gender_inference": {
    "enabled": true,
    "description": "Infer gender from genealogical relations when explicit gender not available",
    "keywords": {
      "female": [
        "filha", "mãe", "mulher", "esposa", "irmã", 
        "madrinha", "viúva", "sogra", "nora", "afilhada", 
        "divorciada", "inventariada", "solteira"
      ],
      "male": [
        "filho", "pai", "marido", "esposo", "irmão",
        "padrinho", "viúvo", "sogro", "genro", "afilhado",
        "divorciado", "inventariado", "solteiro"
      ]
    }
  }
}
```

**Customization:**
- Each project defines language-specific keywords
- Regex word boundaries ensure no partial matches
- Keywords are matched against `person.role` + relation text
- Source is tracked as `gender_source: "inferred"`

---

## Build Process

1. **Load metadata:** Read person/relation JSON files from `projects/{project}/metadata/`
2. **Apply GLOSSARIO:** Merge corrections, identities, and genealogy from GLOSSARIO.md
3. **Infer missing data:**
   - Gender inference using `gender_rules.json` keywords
   - Property/transaction linking
   - Document-person associations
4. **Enrich with gender_source:** Every person gets `gender_source` field
5. **Output:** Write aggregated `docs_logical.json` with all persons and relations
6. **UI display:** All data fetched from `docs_logical.json` (no transformation)

---

## UI Display Strategy

### Golden Rule: Data Drives Display

- **UI reads:** `person.gender`, `person.gender_source` exactly as stored in JSON
- **UI does NOT:** Transform, infer, or compute — only format and display
- **Build outputs:** All computed fields pre-filled in JSON

### Example: Gender Display in UI

```javascript
// In main.html showPerson()
if(p.gender) {
  let label = p.gender === "F" ? "Feminino" : "Masculino";
  if(p.gender_source === 'inferred') label += " (inferred)";
  display(label);  // e.g., "Feminino (inferred)"
}
```

---

## Key Design Principles

1. **Data-driven:** Build computes everything; UI displays only
2. **Language-agnostic:** Code uses English; data (relation text, roles) can be any language
3. **Source-aware:** Track origin of every computed field (`gender_source`, `source`, etc.)
4. **Config-driven:** Inference rules live in project config, not code
5. **No transformation:** UI works directly with JSON structure
6. **Transparent inference:** Users see "(inferred)" labels for computed data
7. **Single source of truth:** `docs_logical.json` is the authoritative output

---

## Examples

### Person with Explicit Gender

```json
{
  "name": "Arlinda Maria",
  "gender": "F",
  "gender_source": "explicit"
}
```
✅ Gender comes from metadata (GLOSSARIO); source is explicit.

### Person with Inferred Gender

```json
{
  "name": "Justina de Jesus",
  "gender": "F",
  "gender_source": "inferred"
}
```
✅ Build inferred gender from relation "filha de Luiz"; UI displays "Feminino (inferred)".

### Person Without Gender

```json
{
  "name": "Miguel António",
  "gender": null
}
```
❌ No explicit gender; relations don't contain gender-indicative keywords; not inferred.

