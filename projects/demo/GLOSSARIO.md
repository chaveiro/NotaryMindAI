# Glossary of Corrections — demo

Project created: 2026-09-19T00:16:31.448955+00:00

Verified local corrections and knowledge used as reading context by OCR/GenAI and applied
in memory by `build_docs_logical.py`. Source files in `metadata/` remain unchanged.

## Reading Corrections

Add confirmed corrections as they are discovered. Use a canonical reading followed by
`NÃO` or `NOT` and each incorrect reading in double quotes. Keep intentional name
variants in `identities` instead of correcting them.

<!--
REAL EXAMPLES FROM THE CÓTIMOS PROJECT (inactive until copied outside this comment):

- **Rabaçal** — NÃO &quot;Cabaçal&quot;.
  Nearby village; confirmed by document context.
- **Joaquim Tomé** — NÃO &quot;Joaquim Ferni&quot;.
  Tomé is a locally attested surname.
- **Liberata Carigas** — NÃO &quot;Liberata Cariças&quot;.
- **sítio do Seixo** — NÃO &quot;Lião&quot;.

Use literal double quotes when activating a correction. The encoded quotes above keep
these examples from being applied to a new project by the deterministic build parser.
-->

## Genealogy (Local Knowledge)

The first name in each identity group is canonical; the remaining names are variants.
Add only people and relations supported by documents or verified local knowledge.
Relation `attribute` values are English schema types; `relation` may preserve the source
language. The build supplies `source: "glossary"` when it is omitted.

<!--
REAL-SHAPED EXAMPLES FROM THE CÓTIMOS PROJECT (inactive reference for editors and GenAI):

Identity group:
["Arlinda Maria", "Rolinda Maria", "Arlinda Maria Dias"]

Person:
{"name":"Arlinda Maria","death":"1979","gender":"F"}

Relation:
{"from":"Luís do Patrocínio Álvaro","to":"Arlinda Maria","relation":"filho de","attribute":"filiation","source":"glossary"}

Useful person fields: name, variants, roles, gender, birth, death, alias, natural,
residencia, profession, burial, notes.

Common relation attributes: filiation, marriage, kinship, affinity, godparent, descent,
inheritance, sale, purchase, mortgage, debt, heir, executor, guardian, witness, other.
-->

```json
{
  "identities": [],
  "persons": [],
  "relations": []
}
```

## Project Notes

- Project directory: `projects/demo`
- Gender inference keywords: `gender_rules.json`
- Consolidated output: `docs_logical.json`

Add archive locations, recurring surnames, historical terminology, and other verified
reading context here. OCR/GenAI should use these notes as guidance but must never invent
facts from them.
