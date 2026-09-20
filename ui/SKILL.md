# Skill: Graph Visualization UI

**Purpose:** Teach agents how to understand, modify, and troubleshoot the NotaryMindAi interactive genealogy visualization.

---

## What Is This UI?

Self-contained interactive web application that visualizes genealogical and property transaction networks from `docs_logical.json`. Built with **vanilla JavaScript + SVG** (zero dependencies), runs entirely in the browser.

**Key characteristic:** All configuration is **centralized in `schema.json`** — no magic strings scattered through code.

---

## What Does It Show?

### Three Synchronized Views

**1. Genealogy View** (default)
- Persons as nodes (colored by gender: pink=F, blue=M, white=unknown)
- Relations as edges (colored by category: blue=filiation, pink=marriage, green=kinship, etc.)
- Generational layout (top-down, oldest generation at top, children centered below parents)
- Dashing indicates confidence: solid=explicit, medium-dash=inferred, heavy-dash=low-confidence, short-dash=glossary

**2. Properties View**
- Properties as nodes (grouped by location)
- Persons involved in sales/mortgages as nodes
- Red edges = sale, Teal edges = mortgage, Blue edges = person appears

**3. Documents View**
- 3-column layout: Persons (left) ↔ Logical Documents (center) ↔ Properties (right)
- Shows which persons appear in which documents and which properties they bought/sold
- Edge colors indicate roles: green=buyer, red=seller, blue=appears

### Interaction
- **Drag nodes** to reposition (with snap-to-generation alignment in genealogy)
- **Mouse wheel** to zoom
- **Middle-mouse drag** to pan
- **Click node/edge** to see detailed panel with full metadata
- **Hover edge** to see relation label
- **Hide categories** with checkboxes at top

### Settings and Project Workflow

The Settings modal has four outer tabs. On mobile, labels collapse to accessible icons.

| Tab | Implemented behavior |
| --- | --- |
| Project | Subtabs for Load, New, and Load External (URL or JSON file); confirmed recursive delete |
| Import Files | Upload supported images/PDFs and show project processing status above the drop zone |
| Build Metadata | Run `ocr`, `reinterpret`, `build`, and `map`; edit glossary/map/consolidated/gender files in the reusable text editor; and display quality reports |

The text editor shows the active filename at bottom-left. Save and expand are on the
bottom-right, with the rightmost `×` button closing the editor. JSON project files are
validated by the API before saving.
| Project Chat | Read-only search against `docs_logical.json` |

Project status uses one shared renderer across all tabs. It shows document, image,
person, relation, and metadata counts. `pending metadata` means an imported source has
no same-stem JSON file; `stale metadata` means the source file is newer than its JSON.
Project Load, Import Files, and Build Metadata default to the project currently loaded
in the viewer, even when it differs from the original URL parameter.

The top header includes person, relation, and property counts. A ready project has no
persistent badge; an incomplete project is amber and shows a warning icon with visible
reasons. The Statistics popup always includes full readiness, image/metadata counts,
map/glossary/consolidated-file presence, pending/stale filenames, timestamp, and model.

All API calls use a JSON-aware fallback helper. It first tries an optional `api` query
parameter, then same-origin `/api`, then local development ports 8787 and 8790. A host
that returns `main.html` for an unknown API route is skipped rather than parsed as JSON.

---

## Architecture: How It Works

### Data Sources

```
docs_logical.json (main data)
├─ persons: [{id, name, gender, birthdate, deathdate, role, variants, ...}]
├─ relations: [{from, to, attribute, relation, source, inference_confidence, ...}]
└─ properties: [{id, description, location, article, value, transmission, ...}]

schema.json (configuration)
├─ ui_version: "2.0.0"
├─ relations: {filiation: {cat, color, dash}, ...}
├─ colors: {F: "#fff0f5", M: "#eff6ff", ...}
├─ layout: {node_width, node_height, genealogy, properties, ...}
├─ filters: {genealogy_default_hidden, doc_role_colors, ...}
└─ ui_strings: {nav_buttons, buttons, status, labels, ...} (50+ strings)
```

### Configuration Loading

1. **Relative path** → `../ui/schema.json`
2. **Fallback** → Hard-coded defaults in main.html

```javascript
async function loadConfigFromCandidates() {
  // Try each candidate URL
  for (const url of candidates) {
    try {
      const resp = await fetch(url);
      if (resp.ok) {
        CONFIG = await resp.json();
        console.log("✅ Config loaded from: " + url);
        return;
      }
    } catch(e) { /* try next */ }
  }
  // If all fail, use fallback defaults
  CONFIG = DEFAULT_CONFIG;
}
```

### UI Initialization (after CONFIG loads)

```javascript
// Set all buttons, labels, titles from CONFIG
if(CONFIG.ui_strings) {
  document.getElementById('vGen').textContent = CONFIG.ui_strings.nav_buttons.genealogy;
  document.getElementById('btnZoomIn').textContent = CONFIG.ui_strings.buttons.zoom_in;
  // ... all UI elements initialized here
}
```

---

## Data Flow

### Image → UI (End-to-End)

```
1. OCR Image
   ↓ (GenAI processes, extracts persons/relations)
   
2. metadata/20260827_*.json
   {
     "from": "António Maria",
     "to": "Francisco Sebastião",
     "attribute": "filiation",        ← Category of relation
     "relation": "filho de",          ← Portuguese label (gender-specific)
     "source": "inferred",
     "inference_confidence": "medium"
   }
   ↓ (build_docs_logical.py consolidates, fills defaults)
   
3. docs_logical.json
   Relations appear as:
   {
     "from": "António Maria",
     "to": "Francisco Sebastião",
     "attribute": "filiation",
     "relation": "filho de",          ← Displayed as-is (no transformation)
     "source": "inferred",
     "inference_confidence": "medium"
   }
   ↓ (Browser loads JSON + CONFIG)
   
4. main.html
   - Reads relation label from JSON: "filho de"
   - Gets color from CONFIG.relations.filiation.color
   - Gets dash from confidence: "3 5" for medium
   - Renders edge with label, color, dashing
```

### Key Point: No Transformations

**Old (wrong):** Relation label stored in metadata, then UI function (inverseRel) regenerated it
**New (correct):** Relation label used as-is from docs_logical.json

---

## Relation Labels (Portuguese)

### How They Get Set

1. **During OCR** → GenAI reads document, extracts: "António é filho de Francisco"
2. **Metadata file** → `"relation": "filho de"` (already gender-specific!)
3. **Build script** → Copies to docs_logical.json as-is
4. **UI** → Displays directly, no transformation

### Examples of Gender-Specific Labels

| Relation | Female | Male | Notes |
|----------|--------|------|-------|
| Filiation | filha de | filho de | Daughter/son of |
| Marriage | casada com | casado com | Married to |
| Widowed | viúva de | viúvo de | Widowed (spouse deceased) |
| Divorced | divorciada de | divorciado de | Divorced from |
| Sibling | irmã de | irmão de | Sister/brother of |
| Heir | herdeira de | herdeiro de | Heiress/heir of |

**UI displays these as-is** from the `relation` field. No logic needed in code.

---

## Configuration: schema.json

### Structure

```json
{
  "ui_version": "2.0.0",
  
  "relations": {
    "filiation": {
      "cat": "filiation",
      "color": "#3b82f6",
      "dash": "0",
      "label_pt": "Filiação"
    }
  },
  
  "colors": {
    "female": "#fff0f5",
    "male": "#eff6ff",
    "unknown": "#f5f5f5"
  },
  
  "layout": { ... },
  
  "filters": { ... },
  
  "ui_strings": { ... }
}
```

### Sections Explained

| Section | Purpose | When to Edit |
|---------|---------|--------------|
| **ui_version** | Version tag | When deploying new UI version |
| **relations** | Relation type definitions | Adding new relation categories or colors |
| **colors** | Color palette | Changing gender colors, backgrounds |
| **layout** | Spacing, sizing parameters | Adjusting node/edge spacing |
| **filters** | View-specific filters and colors | Hiding/showing relation types, role colors |
| **ui_strings** | User-facing text | Changing button labels, error messages, localization |

---

## Spacing Rules & Graph Layout

### Node Dimensions (Common to All Views)

```json
"layout": {
  "node_width": 210,      // All nodes = 210px wide
  "node_height": 64       // All nodes = 64px tall
}
```

**Visual Impact:**
- Larger nodes = more readable text
- Adjust based on screen size or text length
- Node size affects all calculations (edge paths, zoom levels, etc.)

### Genealogy View Spacing

**Configuration:**
```json
"layout": {
  "genealogy": {
    "gap_x": 100,         // Horizontal gap between siblings
    "gap_y": 60,          // Vertical gap between generations
    "padding": 46,        // Canvas edge padding (all sides)
    "couple_gap": 8,      // Gap between married couples (shown side-by-side)
    "sibling_gap": 35     // Extra gap to separate sibling groups
  }
}
```

**Layout Algorithm:**
1. **Generational layers** — Each generation gets one horizontal row, top-down (oldest at top)
2. **Positioning** — Siblings centered below parents, with `couple_gap` between married couples
3. **Horizontal spacing** — Nodes spaced `gap_x` apart, siblings get `sibling_gap` separation
4. **Vertical spacing** — Generations separated by `gap_y` pixels
5. **Canvas bounds** — `padding` pixels margin on all sides

**Interaction:**
- **Drag snap** — Nodes snap to generation row when dragged vertically (4px threshold)
- **Generation lines** — Grid lines show generation boundaries (every `gap_y` pixels)
- **Edge curves** — Bezier curves connect nodes through generation space

**When to Adjust:**
- Too crowded? Increase `gap_x`, `gap_y`, or `node_width`
- Too sparse? Decrease spacing values
- Couples overlapping? Increase `couple_gap`
- Siblings too close? Increase `sibling_gap`

### Properties View Spacing

**Configuration:**
```json
"layout": {
  "properties": {
    "gap_y": 20,          // Vertical gap between property nodes in column
    "col_width": 250,     // Width of each location column
    "pad_x": 40,          // Horizontal canvas padding
    "pad_y": 50           // Vertical canvas padding
  }
}
```

**Layout Structure:**
```
Column 0 (Sellers)     Column 1 (Location A)   Column 2 (Location B)   ...
├─ Person 1            ├─ Property 1           ├─ Property 5
├─ Person 2            ├─ Property 2           ├─ Property 6
└─ Person 3            └─ Property 3

Edges: Person → Property (seller to property)
       Property ← Person (property to buyer)
```

**Positioning:**
1. **Column assignment** — Properties grouped by location (from `pr.location` field)
2. **Column ordering** — Sellers (left), then locations A-Z
3. **Vertical stacking** — Nodes in each column spaced `gap_y` pixels apart
4. **Column spacing** — Columns separated by 30-40px

**Toggle Option:**
- **"Only properties" checkbox** — When enabled, hides seller/buyer persons, shows only property nodes
- Useful for focusing on property transactions

**When to Adjust:**
- Columns too narrow? Increase `col_width`
- Properties overlapping? Increase `gap_y`
- Too much padding? Adjust `pad_x` or `pad_y`

### Documents View Spacing

**3-Column Layout:**
```
Persons (left)         Documents (center)      Properties (right)
├─ Person A            ├─ Document 1           ├─ Property X
├─ Person B            ├─ Document 2           ├─ Property Y
└─ Person C            └─ Document 3           └─ Property Z

Gap between columns: 120px
```

**Spacing Parameters (hardcoded in main.html, line 1404):**
```javascript
const rowH = NODE_H + 16;     // Row height: 64 + 16 = 80px
const PADX = 40;              // Horizontal padding (left/right)
const PADY = 50;              // Vertical padding (top/bottom)
const COLW = NODE_W;          // Column width = 210px (node width)
const GAP = 120;              // Horizontal gap between columns
```

**Column X-Positions:**
```javascript
const colPer = PADX;                    // Person column starts at 40
const colDoc = colPer + COLW + GAP;     // Document column at 370
const colPr = colDoc + COLW + GAP;      // Property column at 700
const canvasWidth = colPr + COLW + PADX; // Total: 950px
```

**Node Colors & Shapes:**
- **Persons** = blue ellipses (#dbeafe) (left column)
- **Documents** = purple rectangles (#e0e7ff) (center column)
- **Properties** = yellow rectangles (#fef9c3) (right column)

**Edge Types & Colors:**
```
Person → Document (role-based coloring)
├─ purchase (green #16a34a, solid line)
├─ sale (red #dc2626, solid line)
└─ aparece/appears (blue #3b82f6, dashed line "4 4")

Document ↔ Property
└─ propriedade (gray #94a3b8, solid line)
```

**Positioning Algorithm:**
1. Documents are sorted by ID, positioned in center column
2. Properties listed per document, stacked vertically in right column
3. Persons aligned by their first appearance in documents, stacked in left column
4. Row height (80px) allows space between stacked nodes

**When to Adjust (editing main.html):**
- Too much space between columns? Change `GAP` value (currently 120)
- Rows too crowded? Increase `rowH` (currently 80)
- Need more padding? Adjust `PADX` or `PADY`

---

## View-Specific Filtering & Colors

### Genealogy View Filters

```json
"filters": {
  "genealogy_default_hidden": [
    "sale",
    "inheritance",
    "mortgage"
  ]
}
```

**Effect:**
- When genealogy view opens, these relation categories are **hidden by default**
- User can toggle checkbox in filter panel to show/hide
- Hiding a category removes its edges from the graph

**Reason:**
- Genealogy focuses on family connections (filiation, marriage, kinship)
- Sale/inheritance/mortgage clutters the genealogy view
- These are better shown in Properties and Documents views
- Users can unhide if needed

### Documents View Role Colors

```json
"filters": {
  "doc_role_colors": {
    "purchase": "#16a34a",     // Green = buyer
    "sale": "#dc2626",         // Red = seller  
    "aparece": "#3b82f6"       // Blue = appears (non-transactional)
  },
  "doc_view": {
    "sale": {"label_pt": "Vendas", "color": "#dc2626"},
    "aparece": {"label_pt": "Pessoas", "color": "#3b82f6"},
    "propriedade": {"label_pt": "Propriedade", "color": "#94a3b8"}
  }
}
```

**How It's Used:**
- Each edge in Documents view gets color based on person's role
- Role determines edge color + whether edge is dashed
- Filter panel shows labels and color indicators

**Edge Styling:**
- Role = "purchase" or "sale" → Solid line, role color
- Role = "aparece" → Dashed line ("4 4"), blue color
- Doc-Property edges → Solid, gray (#94a3b8)

**Customization:**
- Want different role colors? Edit `doc_role_colors` in schema.json
- Want different labels? Edit `doc_view[role].label_pt` values
- Changes apply on page reload

---

## Rendering Performance Notes

### Large Graphs (100+ nodes)

**What can slow down:**
1. **Edge curves** — Bezier path calculations for every edge
2. **Node positioning** — Generational layout computation
3. **Event handlers** — Mouse events on many nodes
4. **SVG rendering** — Too many DOM elements

**Optimization strategies:**
1. Increase `gap_x` or `gap_y` to reduce node density on screen
2. Hide non-essential relation types via filters (genealogy_default_hidden)
3. Use "Only properties" toggle to reduce node count
4. Use browser DevTools Performance tab to profile rendering

### Zoom & Pan Performance

**Implementation:**
- SVG `viewBox` attribute for zoom (no pixel scaling)
- CSS `transform` for panning (GPU-accelerated)
- Mouse wheel listener (50% zoom steps)
- Fit-to-screen recalculates viewBox from node bounds

**Performance:** Native SVG zoom/pan is very fast (no heavy calculation)

---

## How to Modify the UI

### Scenario 1: Change Button Text

**Example:** Change "Properties" to "Propriedades"

1. Open `/workspace/NotaryMindAi/ui/schema.json`
2. Find section `ui_strings.nav_buttons`
3. Change `"properties": "Properties"` → `"properties": "Propriedades"`
4. Reload browser page

**No code change needed.** Button text comes from CONFIG.

### Scenario 2: Change a Color

**Example:** Make female nodes brighter pink

1. Open `schema.json`
2. Find `colors.female`
3. Change from `"#fff0f5"` to `"#ffb3d9"` (or any hex color)
4. Reload page

**Result:** All female nodes now display in new color.

### Scenario 3: Add a New Relation Category

**Example:** Add "business partner" relation

1. Edit `schema.json`, add to `relations`:
   ```json
   "business_partner": {
     "cat": "business_partner",
     "color": "#fbbf24",
     "dash": "0"
   }
   ```

2. Edit metadata files to use new category:
   ```json
   {
     "from": "João",
     "to": "Maria",
     "attribute": "business_partner"
   }
   ```

3. Rebuild: `python3 build_docs_logical.py`

4. Reload page → New relation type appears with yellow color

### Scenario 4: Adjust Graph Spacing (Genealogy)

**Example:** Make genealogy less crowded

1. Open `schema.json`
2. Find `layout.genealogy`
3. Increase values:
   ```json
   "genealogy": {
     "gap_x": 150,         // was 100
     "gap_y": 90,          // was 60
     "sibling_gap": 50     // was 35
   }
   ```
4. Reload page

**Result:** Genealogy view has more space between nodes.

### Scenario 5: Support Multiple Languages

**Example:** Create Portuguese and English configs

1. Create `schema_pt.json` (Portuguese)
2. Create `schema_en.json` (English)
3. Load config based on URL parameter:
   ```javascript
   const lang = new URLSearchParams(window.location.search).get('lang') || 'pt';
   const configFile = `schema_${lang}.json`;
   ```

**Only requires** adding multiple config files and URL parameter logic. UI code unchanged.

---

## UI Strings: Complete List

**Location:** `schema.json` → `ui_strings`

**Categories (50+ total strings):**

### Navigation
- `nav_buttons.genealogy` — "Genealogy"
- `nav_buttons.properties` — "Properties"
- `nav_buttons.documents` — "Documents"

### Buttons (interactive)
- `buttons.zoom_in` — "+ Zoom"
- `buttons.zoom_out` — "- Zoom"
- `buttons.reset` — "↺ Reset"
- `buttons.download` — "Download ⭳"
- `buttons.close` — "Fechar ✕"
- `buttons.previous` — "◀ Anterior"
- `buttons.next` — "Próxima ▶"
- `buttons.copy` — "Copiar"
- `buttons.copy_all` — "Copiar Tudo"

### Status Messages
- `status.loading` — "Carregando..."
- `status.copied` — "✓ Copiado!"
- `status.error_loading` — "Error loading JSON."
- `status.error_processing` — "Error processing data"

**To add a new UI string:**
1. Add key-value pair to appropriate category in `schema.json`
2. In `main.html`, reference it: `CONFIG.ui_strings.category.key`
3. Reload page

---

## Dashing Rules (Edge Visualization)

How edges (relations) are drawn depends on **confidence and source**:

```
Source: "explicit"          → Solid line (dash="0")
Source: "inferred" + high   → Light dash (dash="4", ~2px on 2px off)
Source: "inferred" + medium → Medium dash (dash="3 5", ~3px on 5px off)
Source: "inferred" + low    → Heavy dash (dash="2 4", ~2px on 4px off)
Source: "glossary"          → Short dash (dash="2 4")
```

**Controlled by:** `inference_confidence` field in docs_logical.json

**To change dashing:**
1. Edit `docs_logical.json`, change `inference_confidence` value
2. Reload page

---

## Troubleshooting

### Problem: Buttons show no text

**Cause:** CONFIG not loading, ui_strings initialization failed

**Solution:**
1. Check browser console (F12) for errors
2. Verify `schema.json` is valid JSON (copy to jsonlint.com)
3. Verify URL path is correct
4. Check that `loadConfigFromCandidates()` completed

### Problem: Colors not changing

**Cause:** CONFIG loaded but color override not applied

**Solution:**
1. Verify `schema.json` has `colors` and `relations[].color` sections
2. Check browser DevTools → Elements → inspect node, see inline styles
3. Clear browser cache (Ctrl+Shift+Del)
4. Reload page hard (Ctrl+Shift+R)

### Problem: New relation type not showing

**Cause:** Added to schema.json but not in metadata or build output

**Solution:**
1. Verify `attribute` value in metadata matches `schema.json` relation key
2. Re-run build: `python3 build_docs_logical.py`
3. Check `docs_logical.json` contains new relation type
4. Reload page

### Problem: Graph spacing looks wrong

**Cause:** Spacing values need adjustment, or cached page

**Solution:**
1. Hard reload (Ctrl+Shift+R)
2. Check `schema.json` layout section has reasonable values
3. Try increasing `gap_x` and `gap_y` if nodes overlap
4. Check browser console for JavaScript errors

---

## Requirements

### Browser
- Modern browser with ES6 support (Chrome, Firefox, Safari, Edge)
- SVG support
- Local or network JSON file access

### Server
- **Static:** `python3 -m http.server 8000` or equivalent

### Files
- `docs_logical.json` (data)
- `schema.json` (configuration)
- `main.html` (application)

### No External Dependencies
- Vanilla JavaScript (no jQuery, React, Vue, etc.)
- SVG rendering (browser native)
- Zero npm packages

---

## Editing Workflow

### Typical Modification Cycle

1. **Identify change needed**
   - Text? → Edit `schema.json` → Reload
   - Color? → Edit `schema.json` → Reload
   - Spacing? → Edit `schema.json` → Reload
   - Data? → Edit `metadata/*.json` → Run build → Reload

2. **Make change**
   - Edit file in text editor

3. **Reload page**
  - Browser: Ctrl+R (normal) or Ctrl+Shift+R (hard)

4. **Verify**
   - Open browser DevTools (F12)
   - Check Console for errors
   - Inspect Elements to verify styles applied

### Fast Iteration
- **Keep DevTools open** while editing
- **Use live-reload tool** if available (e.g., LiveServer in VS Code)
- **Use hard reload** (Ctrl+Shift+R) to bypass cache

---

## Examples

### Example 1: Add "cousin" relation
```json
// schema.json
"relations": {
  "cousin": {
    "cat": "kinship",
    "color": "#22c55e",
    "dash": "0"
  }
}
```

### Example 2: Change "Genealogy" button to "Family Tree"
```json
// schema.json
"ui_strings": {
  "nav_buttons": {
    "genealogy": "Family Tree"
  }
}
```

### Example 3: Make genealogy more spacious
```json
// schema.json
"layout": {
  "genealogy": {
    "gap_x": 120,
    "gap_y": 80,
    "sibling_gap": 50
  }
}
```

---

## Key Principles

1. **Configuration First:** Edit `schema.json`, not code
2. **No Transformation:** Relation labels from metadata displayed as-is
3. **Defaults Available:** Code has fallback if CONFIG missing
4. **No Dependencies:** Pure HTML/JS/SVG, runs anywhere
5. **Inspect Everything:** Browser DevTools shows all data and styles
6. **Spacing Matters:** Graph readability depends on proper spacing configuration
7. **Filters Help:** Use genealogy_default_hidden to reduce view clutter

---

## Quick Checklist: When Something Breaks

- [ ] Check browser console (F12) for errors
- [ ] Verify `schema.json` is valid JSON
- [ ] Hard reload page (Ctrl+Shift+R)
- [ ] Clear browser cache
- [ ] Verify file paths are correct
- [ ] Check that build completed successfully
- [ ] Inspect element styles in DevTools
- [ ] Read error message in status area or console
- [ ] Try adjusting spacing if graph looks crowded

---

## Next Steps

1. **View the data:** Open DevTools (F12), inspect `docs_logical.json` structure
2. **Edit schema.json:** Change a button label, reload to verify
3. **Adjust spacing:** Change genealogy gap_x/gap_y values, reload to see impact
4. **Add a relation:** Create test metadata entry, rebuild, verify appearance
5. **Customize colors:** Edit `schema.json` colors section, reload to see changes
