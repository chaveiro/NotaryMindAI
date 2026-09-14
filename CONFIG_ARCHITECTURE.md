# UI Configuration Architecture v2.0

**Date:** 2026-09-14  
**Status:** ✅ PRODUCTION READY

---

## Overview

The NotaryMindAi web UI now uses **centralized JSON configuration** (`schema.json`) instead of hardcoded constants. This enables:

- ✅ **Single source of truth** for all UI configuration
- ✅ **Runtime-configurable** relation types, colors, labels, layout
- ✅ **Language support** (EN + PT labels in schema)
- ✅ **Zero code changes** to add new relation types or modify styling
- ✅ **Easy deployment** across multiple archive projects

---

## Architecture

```
┌─────────────────────────────────────────┐
│        NotaryMindAi UI (main.html)      │
│  • Loads schema.json at startup         │
│  • Uses CONFIG for all styling/layout   │
│  • No hardcoded colors, labels, or gaps │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         schema.json (CONFIG)            │
│  • 23 relation types with colors        │
│  • Layout parameters (gaps, padding)    │
│  • Inference styling (dashes, opacity)  │
│  • UI hints (Portuguese + English)      │
│  • Filter definitions (genealogy, docs) │
│  • Single viewport & node dimensions    │
└─────────────────────────────────────────┘
```

### Initialization Flow

```
main.html loads
    ↓
Async IIFE starts
    ↓
await loadConfig()  ← Fetch schema.json
    ↓
Build CAT_COLOR, CAT_LABEL from CONFIG.relations
    ↓
Initialize NODE_W, NODE_H, SEXO_FILL
    ↓
await load()  ← Fetch docs_logical.json
    ↓
reloadData()  ← Render UI with CONFIG-driven styling
```

---

## schema.json Structure

### Top-Level Keys

| Section | Purpose | Size |
|---------|---------|------|
| `schema_version` | "2.0" | 1 |
| `ui_version` | "2.0" | 1 |
| `name` | Display title | 1 |
| `description` | UI description | 1 |
| `last_updated` | ISO timestamp | 1 |
| **`relations`** | 23 relation type definitions | 23 entries |
| **`groups`** | 6 groupings (genealogy, economic, etc.) | 6 entries |
| **`inference`** | Confidence styling & dash patterns | 2 subsections |
| **`colors`** | Palette (theme colors) | 12 colors |
| **`layout`** | Node sizes, gaps, padding, viewport | 4 subsections |
| **`hints`** | UI help text (3 views) | 3 hints |
| **`filters`** | Default hidden categories & doc filters | 3 subsections |

### `relations` Subsection

Each relation type defines:

```json
{
  "filiation": {
    "label": "Children",           // English display
    "label_pt": "Filhos",          // Portuguese display
    "color": "#2563eb",            // Hex color code
    "group": "genealogy",          // Grouping (for filtering)
    "attributes": []               // Valid optional fields for this relation
  }
}
```

**All 23 types:**
- genealogy (7): filiation, marriage, kinship, affinity, godparent, descent, inheritance
- economic (4): sale, purchase, mortgage, debt
- succession (4): heir, legatee, executor, testator
- legal (5): guardian, ward, procurator, principal, witness
- legitimation (2): legitimated, acknowledged
- other (1): other

### `layout` Subsection

```json
{
  "node_width": 210,
  "node_height": 64,
  "viewport_padding": 40,
  "genealogy": {
    "gap_x": 100,         // Horizontal gap between nodes
    "gap_y": 60,          // Vertical gap between generations
    "padding": 46,        // Border padding
    "couple_gap": 8,      // Gap between spouses
    "sibling_gap": 35     // Gap between siblings
  },
  "properties": {
    "gap_y": 20,
    "col_width": 250,
    "pad_x": 40,
    "pad_y": 50
  }
}
```

### `inference` Subsection

Confidence-based dash patterns:

```json
{
  "confidence_styles": {
    "high": { "dash": "4", "stroke": "2.2", "opacity": "1" },
    "medium": { "dash": "3 5", "stroke": "2", "opacity": "0.8" },
    "low": { "dash": "2 4", "stroke": "1.8", "opacity": "0.6" }
  },
  "special_dashes": {
    "glossary": { "dash": "2 4" },
    "divorce": { "dash": "9 4" },
    "descent": { "dash": "6 5" },
    "explicit": { "dash": "0" }
  }
}
```

### `filters` Subsection

```json
{
  "genealogy_default_hidden": ["sale", "inheritance", "mortgage"],
  "doc_view": {
    "sale": { "label": "Vendas", "color": "#dc2626" },
    "aparece": { "label": "Pessoas", "color": "#3b82f6" },
    "propriedade": { "label": "Propriedade", "color": "#94a3b8" }
  },
  "doc_role_colors": {
    "purchase": "#16a34a",
    "sale": "#dc2626",
    "aparece": "#3b82f6"
  }
}
```

---

## Code Integration

### Loading Configuration

```javascript
// In loadConfig()
let CONFIG = null;

async function loadConfig() {
  const response = await fetch('schema.json');
  CONFIG = await response.json();
  
  // Initialize derived variables
  NODE_W = CONFIG.layout.node_width;
  NODE_H = CONFIG.layout.node_height;
  
  // Build color maps
  CAT_COLOR = Object.fromEntries(
    Object.entries(CONFIG.relations).map(([k, v]) => [k, v.color])
  );
  CAT_LABEL = Object.fromEntries(
    Object.entries(CONFIG.relations).map(([k, v]) => [k, v.label])
  );
  
  // Gender-based node colors
  SEXO_FILL = {
    F: CONFIG.colors.node_fill_female,
    M: CONFIG.colors.node_fill_male,
    "": CONFIG.colors.node_fill_unknown
  };
}
```

### Using Configuration in Code

**Layout values:**
```javascript
const GAPX = CONFIG.layout.genealogy.gap_x;
const GAPY = CONFIG.layout.genealogy.gap_y;
```

**Hints:**
```javascript
document.getElementById("barHint").textContent = 
  v === "gen" ? CONFIG.hints.genealogy 
  : v === "prop" ? CONFIG.hints.properties 
  : CONFIG.hints.documents;
```

**Filters:**
```javascript
if(v === "gen") {
  CONFIG.filters.genealogy_default_hidden.forEach(cat => hidden.add(cat));
}
```

**Document filters:**
```javascript
const doc_filters = CONFIG.filters.doc_view;
Object.entries(doc_filters).forEach(([c, cfg]) => {
  // Create filter buttons with cfg.color and cfg.label
});
```

**Role colors:**
```javascript
const col = CONFIG.filters.doc_role_colors[v.role] || "#3b82f6";
```

---

## Customization Guide

### Add a New Relation Type

1. Update `schema.json` → `relations`:
```json
"mynewtype": {
  "label": "New Type",
  "label_pt": "Novo Tipo",
  "color": "#color_hex",
  "group": "economic",
  "attributes": ["field1", "field2"]
}
```

2. **No code changes needed.** UI automatically picks it up:
   - Color from `CONFIG.relations.mynewtype.color`
   - Label from `CAT_LABEL['mynewtype']` (derived at load)
   - Filters automatically include it

### Change Colors

Edit `schema.json` → `relations[*].color` (hex values)  
Edit `schema.json` → `colors.*` (theme palette)

Colors are loaded at startup, so no code compilation needed.

### Modify Layout Gaps

Edit `schema.json` → `layout.genealogy` or `layout.properties`:
```json
"gap_x": 120,  // Increase horizontal spacing
"gap_y": 80,   // Increase vertical spacing
"couple_gap": 12  // Increase spouse spacing
```

Changes apply on next page load.

### Add/Modify Hints

Edit `schema.json` → `hints`:
```json
"genealogy": "Your custom hint text here"
```

### Add Inference Confidence Level

Edit `schema.json` → `inference.confidence_styles`:
```json
"very_high": { "dash": "0", "stroke": "3", "opacity": "1" }
```

Use in dashing logic with `r.inference_confidence === "very_high"`.

---

## Deployment

### Prerequisites
- ✅ `ui/schema.json` in same directory as `main.html`
- ✅ `ui/main.html` updated (v2.0, uses CONFIG)
- ✅ `projects/<project>/docs_logical.json` accessible (v2.0 format)

### Static Server (Local)
```bash
cd /workspace/NotaryMindAi
python3 -m http.server 8000 --directory .

# Open in browser:
http://localhost:8000/ui/main.html?project=cotimos
```

### Piclaw (Production)
- Deploy updated `ui/main.html` and `ui/schema.json`
- Serve `projects/<project>/docs_logical.json` via piclaw
- schema.json loaded from HTTP (same origin)

---

## Troubleshooting

### "schema.json not found"
- Ensure `schema.json` is in `ui/` folder
- Check browser console for CORS errors if served from different origin
- If using static server, ensure correct `--directory` parameter

### Colors/layout not updating
- Clear browser cache (Ctrl+Shift+Delete)
- Check schema.json is valid JSON (use `python3 -m json.tool schema.json`)
- Verify CONFIG is loaded: open DevTools console, type `CONFIG`

### Relation type not appearing
- Check `CONFIG.relations` has the type (DevTools console)
- Verify data file (`docs_logical.json`) has relations with `attribute` matching schema key
- Check filters: might be hidden by default

---

## Files

| File | Purpose | Size |
|------|---------|------|
| `ui/schema.json` | **Config** (relations, layout, colors, hints, filters) | 7.8 KB |
| `ui/main.html` | **UI code** (reads schema.json, consumes CONFIG) | 92 KB |
| `projects/<project>/docs_logical.json` | **Data** (v2.0 schema, top-level persons/relations) | Variable |

---

## Summary

✅ **Centralized configuration** eliminates hardcoded magic strings  
✅ **Schema-driven** styling and layout  
✅ **Zero code changes** to customize for new projects  
✅ **Multi-language support** (EN + PT in schema)  
✅ **Production ready** with v2.0 docs_logical.json  

**Status: READY FOR DEPLOYMENT** 🚀

