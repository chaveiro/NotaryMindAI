# Transcription & Consolidation Skill

## Quick Reference

### Essential Commands

```bash
# List pending images
bun skills/transcript/find_new_docs.ts projects/cotimos

# Build consolidated JSON
cd projects/cotimos && python3 ../../skills/transcript/build_docs_logical.py . && jq empty docs_logical.json

# Validate the document map
python3 ../../skills/transcript/validate_map.py projects/cotimos

# Validate the consolidated output
python3 ../../skills/transcript/validate_docs.py projects/cotimos
```

---

## Processing Operations

### `ocr`: New/Reprocess Documents with GenAI

**When:** New images added to `imported/` or need retranscription  
**Model Required:** `github-copilot/claude-opus-4.8` (check before starting)

**Visual OCR (read the image)**
- GenAI reads photo or pdf → creates `metadata/<name>.json`
- Fill: `full_transcript`, `entities`, `properties`, `persons`, `relations`
- **Critical:** Each seller/buyer/creditor must be in `persons[]` with explicit role + one relation per person in `relations[]`
- Follow SCHEMA.md rules
- Consider corrections or local knowledge from `projects/<name>/GLOSSARIO.md` if existent

### `reinterpret`: Reinterpret Existing Transcription
- GenAI reads `metadata/<name>.json` `full_transcript` → updates `entities`, `properties`, `persons`, `relations`
- Use when text interpretation needs fixing (without re-photographing)
- Follow SCHEMA.md rules
- Consider corrections or local knowledge from `projects/<name>/GLOSSARIO.md` if existent
- 
**Workflow:**
1. List pending: `bun skills/transcript/find_new_docs.ts projects/cotimos`
2. Ask user: "Process X pending images via GenAI?"
3. Create `metadata/` JSON files (`ocr` or `reinterpret`)
4. Continue to `map`

---

### `build`: Regenerate Consolidated Data

**When:** After changing metadata, the glossary, or the document map  
**Inputs:** `metadata/*.json`, `GLOSSARIO.md`, `docs_logical_map.json`
**Output:** `projects/cotimos/docs_logical.json`

Glossary corrections and local knowledge are applied during this deterministic build.

**Two types of entries:**
- **Corrections** — `**Canonical** — NOT "Wrong"` (applied in-memory during build)
- **Local Knowledge** — JSON block with `identities`, `persons`, `relations` (source:"glossary")

**New-project template:** `skills/transcript/GLOSSARY-TEMPLATE.md` is the source copied and
personalized as `projects/<name>/GLOSSARIO.md` when the API/UI creates a project. It is
modeled on the Cótimos project, with verified reading corrections, structured local
genealogy, and project notes. Real Cótimos examples are commented/inert for the build
but remain readable context for editors and OCR GenAI. The first valid `json` block
contains empty `identities`, `persons`, and `relations` arrays until project facts are
known.

The generated project `GLOSSARIO.md`, not the root template, is consumed directly by
`build_docs_logical.py` and supplied as context to `ocr`, `reinterpret`, and `map` GenAI runs.

The builder reads the first valid fenced `json` object containing one of those three
keys. Keep all structured local knowledge in that single block.

**Workflow:**
1. Edit `GLOSSARIO.md`
2. Regenerate: `python3 ../../skills/transcript/build_docs_logical.py projects/cotimos`
3. Validate: `python3 ../../skills/transcript/validate_map.py projects/cotimos`

### `validate-docs`: Validate Consolidated Output

**When:** Confirm that the generated `docs_logical.json` is structurally consistent
after `build`. This checks the final output, while `validate_map.py` checks the
intermediate `docs_logical_map.json`.

**Command:** `python3 ../../skills/transcript/validate_docs.py projects/cotimos`

---

### `map`: Update Logical Document Map (No Re-OCR)

**When:** Need to group images → documents or fix transaction data  
**File:** `projects/cotimos/docs_logical_map.json`

The only top-level document collection is `logical_documents`, as specified in
`SCHEMA.md`. Do not use `documents` in the map; that key belongs to generated
`docs_logical.json` output only.

**Workflow:**
1. GenAI reads `full_transcript` from metadata → deduces:
   - Document grouping (which images = one logical document)
   - `title`, `type`, `continuation`, `transaction`
2. Write result conforming to SCHEMA.md
3. Regenerate: `python3 ../../skills/transcript/build_docs_logical.py projects/cotimos`
4. Validate: `python3 ../../skills/transcript/validate_map.py projects/cotimos` (must be 0 errors)

**Relation Extraction Checklist (Language-Agnostic):**

For EACH relation found in the document:
- [ ] `from`: Origin person name
- [ ] `relation`: Source language text (Portuguese: "vende a", "filho de", etc.)
- [ ] `to`: Target person name
- [ ] `attribute`: ENGLISH relation type (filiation|marriage|sale|purchase|mortgage|kinship|affinity|godparent|heir|executor|guardian|witness|other, etc.)
- [ ] `source`: "explicit" (from document) or "inferred" (derived from context)
- [ ] `inferedbyai`: true if you marked as inferred; false if explicit
- [ ] `inference_type`: explicit|inferred_same_doc|inferred_cross_doc (for inferred only)
- [ ] `inference_confidence`: high|medium|low (for inferred only: your assessment of certainty)
- [ ] `inference_reasoning`: Text explaining WHY you inferred (for inferred only)
- [ ] Transaction attributes if applicable: seller, buyer, value, label, date, date_precision, date_original

**Transaction Checklist:**
- [ ] Each seller/buyer/creditor is in `persons[]` (with explicit role)
- [ ] One relation per individual in `relations[]` with correct `attribute` field
- [ ] `attribute` field uses English type (sale|purchase|mortgage|debt), not language-specific text
- [ ] Transaction attributes included: seller, buyer, value, label, date, date_precision, date_original
- [ ] Both ends exist (build validation catches orphans)
- [ ] Transaction labels extracted from document (not too generic)

---

## Rules (Non-Negotiable)

1. **Always ask before modifying** metadata, map, or glossary
2. **`docs_logical.json` is source of truth** — never hand-edit, regenerate via build
3. **`metadata/*.json` are immutable** — only change via GenAI (`ocr`/`reinterpret`)
4. **GLOSSARIO.md applied in-memory** — doesn't edit originals
5. **Never invent** — mark uncertain as `[?]`, illegible as `[illegible]`
6. **Schema** — field names are English (genealogy, persons, relations, etc.)
7. **Relation `attribute` field** — REQUIRED: use English type (filiation, sale, etc.), keep `relation` text in source language
8. **Model:** Always verify `github-copilot/claude-opus-4.8` before OCR


---

## Files You'll Work With

| File | Role | Mutability |
| --- | --- | --- |
| projects/image/imported/* | Raw images or PDFs | Read-only |
| projects/image/metadata/*.json | OCR output | Write via GenAI only |
| projects/image/docs_logical_map.json | Document map | Edit or GenAI-generate |
| projects/image/docs_logical.json | Source of truth | Read-only (generated) |
| projects/image/GLOSSARIO.md | Corrections & local knowledge | Edit freely + rebuild |
| `skills/transcript/SCHEMA.md` | Data contract | Immutable |
   ```
6. **Report:** "Build: X DL, Y images | Validation: 0 errors ✅"

---

## 👥 Agent Instructions: Extracting Relations & Variants

### Confidence Levels

When marking relations or variants, assess your confidence:

- **`high` (85%+):** Very confident, clear context or explicit statement
- **`medium` (60-85%):** Reasonably confident, some context but some uncertainty
- **`low` (40-60%):** Uncertain but worth recording, speculative but plausible

**Examples:**
- "Document explicitly states: 'João and Maria were married in 1825'" → high confidence
- "Document says 'Mr João and his wife'; someone named Maria appears in family list later" → medium/high confidence
- "João appears as seller in one deed, Paulo as executor in another; could be related" → low confidence

### When to Mark Relations as Inferred (`inferedbyai: true`)

Mark a relation as inferred ONLY when it's NOT explicitly stated but derived from context:

**Example 1: Explicit Marriage**
```json
{
  "from": "João",
  "to": "Maria",
  "relation": "casado com",
  "attribute": "marriage",
  "source": "explicit",
  "inferedbyai": false,
  "inference_type": "explicit"
}
```
Reason: Document explicitly states they are married.

**Example 2: Inferred Marriage (Same Document)**
```json
{
  "from": "João",
  "to": "Filipa",
  "relation": "casado com",
  "attribute": "marriage",
  "source": "inferred",
  "inferedbyai": true,
  "inference_type": "inferred_same_doc",
  "inference_confidence": "medium",
  "inference_reasoning": "Document states 'Mr João and his wife'; female name Filipa appears in family witness section. Inferred marriage based on proximity and context."
}
```
Reason: Not explicitly stated, but inferred from "Mr João and his wife" context.

**Example 3: When NOT to Infer**
```
Document mentions: "João da Silva" and separately "Filipa da Costa"
DO NOT infer marriage without more context.

If you really think they're related, mark with LOW confidence:
{
  "inference_confidence": "low",
  "inference_reasoning": "Names appear in same document but no explicit connection stated. Unclear if related."
}
```

### Variant Grouping with Confidence

When a person appears with different name forms:

**Example 1: High Confidence Variant**
```json
{
  "name": "João",
  "roles": ["seller", "testator"],
  "variants": [
    {
      "name": "João da Silva",
      "source": "document_context",
      "confidence": "high",
      "reasoning": "Full name 'João da Silva' appears in deed opening clause; same person as 'João' in transaction list (consistent context)"
    }
  ]
}
```
Reason: Very likely same person (full name vs. first name in same document).

**Example 2: Medium Confidence Variant**
```json
{
  "name": "João",
  "variants": [
    {
      "name": "João S.",
      "source": "signature_page",
      "confidence": "medium",
      "reasoning": "Abbreviated signature 'J.S.'; likely same person but initials only"
    }
  ]
}
```
Reason: Probably same person, but abbreviated form is less certain.

**Example 3: Low Confidence Variant**
```json
{
  "name": "João",
  "variants": [
    {
      "name": "João",
      "source": "different_document",
      "confidence": "low",
      "reasoning": "Same name in different document; could be same person or namesake (unclear without additional context)"
    }
  ]
}
```
Reason: Same name in different document, but unclear if same person.

### Relation Type Examples

#### Genealogy Relations (No transaction attributes)

**Filiation (Parent-Child)**
```
Document: "João, son of Pedro da Silva"
JSON:
{
  "from": "João",
  "to": "Pedro da Silva",
  "relation": "filho de",
  "attribute": "filiation",
  "source": "explicit"
}
```

**Marriage**
```
Document: "João and Maria were married in 1825"
JSON:
{
  "from": "João",
  "to": "Maria",
  "relation": "casado com",
  "attribute": "marriage",
  "date": "1825-01-01",
  "date_precision": "year",
  "date_original": "1825",
  "source": "explicit"
}
```

**Kinship (Siblings)**
```
Document: "The testator's brother João and sister Maria"
JSON:
{
  "from": "João",
  "to": "testator",
  "relation": "irmão de",
  "attribute": "kinship",
  "source": "explicit"
}
```

#### Economic Relations (with transaction attributes)

**Sale**
```
Document: "João dos Santos sold a property to Maria Silva for 100 réis on 15 May 1850"
JSON:
{
  "from": "João dos Santos",
  "to": "Maria Silva",
  "relation": "vende a",
  "attribute": "sale",
  "label": "venda de propriedade",
  "seller": "João dos Santos",
  "buyer": "Maria Silva",
  "value": "100 réis",
  "date": "1850-05-15",
  "date_precision": "day",
  "date_original": "fifteenth day of May",
  "source": "explicit"
}
```

**Mortgage/Debt**
```
Document: "João mortgaged his property to the Bank for 500 réis"
JSON:
{
  "from": "João",
  "to": "Bank",
  "relation": "hipoteca de",
  "attribute": "mortgage",
  "label": "hipoteca de propriedade",
  "mortgagor": "João",
  "mortgagee": "Bank",
  "value": "500 réis",
  "source": "explicit"
}
```

#### Succession Relations (Wills & Formal Partitions)

**Inheritance (Legítima / Quinhão Hereditário / Lote)**
```
Portuguese documents distinguish:
- Legítima: Legal/mandatory share of estate
- Quinhão hereditário: Assigned share in formal partition
- Lote: Specific bundle/lot in estate partition

Document: "Formal de partilhas: Lote C assigned to Rolinda Maria from estate of Luiz do Nascimento Dias (†1898)"
JSON (in map.json):
{
  "nature": "inheritance",
  "heir": "Arlinda Maria",           // Use GLOSSARIO canonical name
  "from": "Luiz do Nascimento Dias", // Deceased (include death year if known)
  "value": "Lote C" or "1/3 share",  // Portion description or value
  "label": "Lote C de Arlinda Maria no inventário de Luiz do Nascimento Dias (†1898)"
}

JSON (in relations array):
{
  "from": "Arlinda Maria",
  "to": "Luiz do Nascimento Dias",
  "relation": "herança de",
  "attribute": "inheritance",
  "label": "Lote C (quinhão hereditário)",
  "value": "?" (extract if possible),
  "source": "explicit"
}
```

**Heir**
```
Document: "I leave all property to my son Pedro"
JSON:
{
  "from": "testator",
  "to": "Pedro",
  "relation": "deixa a",
  "attribute": "heir",
  "label": "herdeiro na sucessão de testador",
  "source": "explicit"
}
```

**Executor**
```
Document: "I appoint my brother-in-law Paulo as executor of this will"
JSON:
{
  "from": "Paulo",
  "to": "testator",
  "relation": "testamenteiro de",
  "attribute": "executor",
  "label": "executor do testamento",
  "source": "explicit"
}
```

#### Legal/Judicial Relations

**Guardian**
```
Document: "The minor João was placed under guardianship of his uncle Pedro"
JSON:
{
  "from": "Pedro",
  "to": "João",
  "relation": "tutor de",
  "attribute": "guardian",
  "label": "tutor de menores",
  "source": "explicit"
}
```

**Witness**
```
Document footer: "Witnessed by: João da Silva, Maria Santos"
JSON:
{
  "from": "João da Silva",
  "to": "document",
  "relation": "testemunha de",
  "attribute": "witness",
  "label": "testemunha",
  "source": "explicit"
}
```

### Date Normalization

Always normalize dates to YYYY-MM-DD:

**Examples:**

| Input | Normalized | Precision | Original |
|---|---|---|---|
| "Fifteenth day of May, year of our Lord eighteen hundred fifty" | 1850-05-15 | day | Fifteenth day of May |
| "May 1850" | 1850-05-01 | month | May 1850 |
| "In the year 1850" | 1850-01-01 | year | In the year 1850 |
| "Circa 1850" or "About 1850" | 1850-01-01 | approximate | Circa 1850 |
| (no date found) | (omit field) | (omit field) | (omit field) |

### Transaction Label Extraction

Extract meaningful noun phrases from document text describing the transaction:

**Good labels:**
- ✅ "venda de propriedade" (describes what is sold)
- ✅ "hipoteca de terras em Cótimos" (specific asset + location)
- ✅ "compra de casa com quinta" (specific assets)

**Bad labels:**
- ❌ "vende a" (too generic)
- ❌ "According to the deed..." (narrative, not label)
- ❌ "" (empty)

Usually the first sentence or transaction heading contains the best label.

### Property Reference Linking (for Transaction Relations)

**CRITICAL for economic/inheritance relations:**

Every transaction relation (with `attribute` in `sale`, `purchase`, `mortgage`, `debt`, `inheritance`) MUST link to the property(ies) it involves.

**Add `property` field with property description:**
```json
{
  "from": "João",
  "to": "Maria",
  "attribute": "sale",
  "property": "tiled house with five rooms on Commerce Street",  // ← REQUIRED
  "seller": "João",
  "buyer": "Maria",
  "value": "100 réis",
  "label": "venda de propriedade"
}
```

**Linking strategy:**
- Match property `description` field from `properties[]` array
- If single property in document → link automatically
- If multiple properties → use fuzzy matching on description + value context
- If ambiguous → use best match from properties array
- If no match → omit `property` field (optional fallback)

**Property matching examples:**
```json
// Document has 1 property:
{
  "description": "Terreno de regadio e oliveiras",
  "value": "1.378$00",
  ...
}

// Relation links to it:
{
  "attribute": "sale",
  "value": "1.378$00",
  "property": "Terreno de regadio e oliveiras"  // ← Matched by description + value
}
```

### Handling Uncertainty

When uncertain:

**Option 1: Mark with low confidence**
```json
{
  "from": "João",
  "to": "Maria",
  "attribute": "marriage",
  "source": "inferred",
  "inferedbyai": true,
  "inference_confidence": "low",
  "inference_reasoning": "Unclear connection; recording with low confidence for review"
}
```

**Option 2: Omit entirely**
If you're very unsure, omit the relation rather than guess.

---

## Image JSON Schema (For Reference)

```json
{
  "image": "filename.jpg",
  "document_type": "will|deed|inventory|...",
  "document_date": "1850-05-15",
  "location": "Cótimos, Portugal",
  "full_transcript": "Full text transcription...",
  "entities": {
    "names": ["João da Silva", "Maria [?]"],
    "dates": ["1850-05-15"],
    "places": ["Cótimos"],
    "values": ["200 réis"]
  },
  "properties": [
    {
      "description": "tiled house",
      "location": "Commerce Street",
      "article": 6,
      "value": "45 escudos",
      "confrontations": {"north": "José's house", "south": "path"}
    }
  ],
  "persons": [
    {
      "name": "João",
      "roles": ["seller", "testator"],
      "variants": [
        {
          "name": "João da Silva",
          "source": "document_context",
          "confidence": "high",
          "reasoning": "Full name appears in opening clause"
        }
      ]
    },
    {
      "name": "Maria",
      "roles": ["buyer"]
    }
  ],
  "relations": [
    {
      "from": "João",
      "to": "Maria",
      "relation": "filha de",                    // Source language (for display)
      "attribute": "filiation",                 // English type (for classification) — REQUIRED
      "source": "explicit",
      "inferedbyai": false,
      "inference_type": "explicit",
      "inference_confidence": "high"
    },
    {
      "from": "João",
      "to": "Maria",
      "relation": "vende a",
      "attribute": "sale",                      // Use this, not category
      "label": "venda de propriedade",
      "source": "explicit",
      "inferedbyai": false,
      "inference_type": "explicit",
      "seller": "João",
      "buyer": "Maria",
      "value": "200 réis",
      "date": "1850-05-15",
      "date_precision": "day",
      "date_original": "fifteenth day of May"
    }
  ],
  "ocr_metadata": {
    "genai_model": "github-copilot/claude-opus-4.8",
    "method": "visual_ocr|reinterpretation",
    "ocr_confidence": "high|medium|low",
    "status": "complete",
    "notes": "Any processing notes"
  }
}
```

---

## Common Issues & Fixes

| Problem | Solution |
|---------|----------|
| "Pending images found" | Run `ocr` on those images |
| "Validation error: missing_tx_relations" | Re-run `reinterpret` on the image to extract genealogy |
| "Validation error: tx_relation_orphan" | Seller/buyer missing from genealogy.persons |
| "JSON invalid" | Run `jq empty docs_logical.json` to see error |
| "Build fails" | Check GLOSSARIO.md syntax or run with verbose flag |

---

## Key Constraints

- **Persons & relations** — Top-level arrays in metadata JSON (no genealogy wrapper)
- **Roles** — Array field (person can have multiple roles: seller, testator, buyer, heir, witness, etc.)
- **Transaction data** — Now attributes on relations (seller, buyer, value, label, date, etc.)
- **Inference marking** — `inferedbyai: true` (agent-marked), `infered: true` (build script from GLOSSARIO)
- **Variant grouping** — Track with source, confidence, reasoning; GLOSSARIO links them during build
- **Canonical relation types** — ~22 types (genealogy 7, economic 4, succession 4, legal 5, legitimation 2, other 1)
- **Dates** — Always normalize to YYYY-MM-DD, YYYY-MM-DD HH:MM:SS or HH:MM:SS with `date_precision` (day|month|year|century) + `date_original` (UI label)
- **Names** — Preserve variants as found; don't force uniformity
- **Transaction labels** — Extract meaningful noun phrases from document text
- **Source marking** — Distinguish explicit vs. inferred with confidence levels
