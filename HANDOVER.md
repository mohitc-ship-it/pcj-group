# Handover Documentation

## Quick Start

```bash
# 1. Clone and setup
cd swanky_women
pip install -r requirements.txt
cp .env.example .env
# Add your API keys to .env

# 2. Place garment images
# Put front.png and back.png in assets/

# 3. Edit context in main.py (__main__ block)
# Set brand, collection, season, fabric, size range

# 4. Run
export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib"  # macOS only
python main.py

# Output: Tech_Pack.pdf in swanky_women/
```

## Key Files to Modify

| Task | File | What to change |
|------|------|---------------|
| Change LLM model | `llm.py:20` | `DEFAULT_MODEL` variable |
| Add garment categories | `main.py:265-266` | Vision agent prompt — garment type list |
| Change detail prompts | `main.py:1546-1582` | `page2_prompt` — controls detail text style/length |
| Modify PDF layout | `templates/*.html` | HTML/CSS per page |
| Change page structure | `data/master.json` | Base template defining all page fields |
| Add/remove PDF pages | `generate.py:100-110` | `PAGES` list — template-to-filename mapping |
| Adjust color matching | `utils.py` | `recommend_colors_from_images()` — LAB color logic |
| Change image generation | `imageGen.py` | Gemini prompts for sketches/labels |

## How the Pipeline Works

```
Input (images + context)
    │
    ├── 1. Header Agent → style code, metadata
    ├── 2. Logo Generation → brand logo image
    ├── 3. Color Agent → dominant color + Pantone TCX palette
    ├── 4. Vision Agent → raw garment observation text
    ├── 5. Classification Agent → category, complexity, fit type
    ├── 6. Fabric Decision Agent → composition, GSM, finish
    ├── 7. Construction Agent → seams, stitches, machines
    ├── 8. Measurement Agent → POMs, tolerances, size chart
    ├── 9. Resolver Agent → cross-field consistency check
    ├── 10. Verifier Agent → final validation
    │
    ├── Image Generation
    │   ├── Technical sketch (front + back with labels)
    │   ├── Brand label
    │   ├── Care label
    │   └── Measurement diagram
    │
    ├── Grid Generation → detail close-up images
    │
    ├── Data Assembly → master_filled.json
    │
    └── PDF Rendering
        ├── 9 HTML templates rendered via Jinja2
        ├── Each converted to PDF via WeasyPrint
        └── Merged into final Tech_Pack.pdf
```

## Data Flow

All agent outputs are assembled into `data/master_filled.json`. This JSON file is the single source of truth for PDF rendering.

- `generate_techpack()` in `main.py` populates `master_filled.json`
- `generatePdf()` in `generate.py` reads it and renders templates
- To re-render PDF without re-running AI: call `generatePdf()` directly

## Adding a New Garment Category

1. Add the category name to the vision agent prompt in `main.py:265-266`
2. If the category needs unique measurement points, update the measurement agent prompt
3. If the category needs unique construction logic, update the construction agent prompt
4. Test with a sample image of that category

## Modifying a PDF Template

Templates are in `templates/`. Each is standalone HTML with embedded CSS.

- Page size is set via `@page { size: 1240px 840px; }`
- Data is injected via Jinja2: `{{ header.brand }}`, `{{ page_2.details }}`, etc.
- Images use relative paths: `{{ page_3.technical_sketch_img }}`
- After editing, run `generatePdf()` to see changes (no need to re-run AI)

**Important:** WeasyPrint has limited CSS support. Avoid CSS Grid (use Flexbox), avoid complex `overflow` rules, and always use explicit pixel heights for containers.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| WeasyPrint import error | Set `DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib"` |
| `front.png` not found | Image generation step may overwrite input files. Keep backups with timestamps. |
| PDF has more than 9 pages | Content overflows. Reduce text length in prompts or check template CSS heights. |
| Wrong garment classification | Add the garment type to vision agent prompt (`main.py:265-266`) |
| Care label shows wrong fabric | The care label IMAGE is generated separately. Re-run with `generate=True` to regenerate. |
| API 404 error | Check model name in `llm.py:20`. Only models your API key has access to will work. |
