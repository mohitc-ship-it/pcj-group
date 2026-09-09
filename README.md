# PCJ Group — AI-Powered Tech Pack Generator

An AI system that generates complete 9-page Technical Package PDFs from garment photographs. Input two images (front + back) with basic context and receive a factory-oriented tech pack in minutes.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (React)                   │
│            Upload images + context input              │
└──────────────────────┬──────────────────────────────┘
                       │ API
┌──────────────────────▼──────────────────────────────┐
│                Backend (FastAPI)                      │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │            AI Agent Pipeline                 │    │
│  │                                             │    │
│  │  1. Header Agent ──► Style code, metadata   │    │
│  │  2. Color Agent ───► Pantone TCX matching   │    │
│  │  3. Vision Agent ──► Garment analysis       │    │
│  │  4. Classification ► Category, complexity   │    │
│  │  5. Fabric Agent ──► Composition, GSM       │    │
│  │  6. Construction ──► Seams, stitches        │    │
│  │  7. Measurement ───► POMs, size chart       │    │
│  │  8. Resolver Agent ► Cross-field verify     │    │
│  │  9. Verifier Agent ► Final consistency      │    │
│  └─────────────────────────────────────────────┘    │
│                       │                              │
│  ┌────────────────────▼────────────────────────┐    │
│  │         Image Generation (Gemini)            │    │
│  │  Technical sketch, labels, care symbols      │    │
│  └─────────────────────────────────────────────┘    │
│                       │                              │
│  ┌────────────────────▼────────────────────────┐    │
│  │       PDF Rendering (Jinja2 + WeasyPrint)    │    │
│  │  9 HTML templates → 9 pages → merged PDF     │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite + TypeScript |
| Backend | Python, FastAPI |
| LLM | Claude (Anthropic API) — structured outputs via Pydantic |
| Image Gen | Google Gemini via OpenRouter |
| PDF Engine | Jinja2 templates + WeasyPrint |
| Color Science | LAB color space, Delta-E matching, scikit-learn |

## Project Structure

```
pcj-group/
├── frontend/
│   └── PCJ-frontend/          # React app (Vite + TypeScript)
│
├── swanky_women/               # Backend — AI pipeline + PDF generation
│   ├── main.py                 # Core pipeline — all AI agents
│   ├── llm.py                  # LLM client (Anthropic Claude)
│   ├── models.py               # Pydantic models for structured output
│   ├── generate.py             # PDF generation (Jinja2 → WeasyPrint → merged PDF)
│   ├── imageGen.py             # Image generation (technical sketch, labels)
│   ├── utils.py                # Color extraction, image processing utilities
│   ├── app.py                  # FastAPI server
│   ├── editor_api.py           # API for template editing
│   │
│   ├── templates/              # HTML/CSS templates (9 pages)
│   │   ├── intro_page.html
│   │   ├── 3d_cad_design_page.html
│   │   ├── technical_sketch_page.html
│   │   ├── accessories_page.html
│   │   ├── product_construction.html
│   │   ├── measurements.html
│   │   ├── fabrics_quality_standards.html
│   │   ├── size_chart_page.html
│   │   └── wash_and_care_label.html
│   │
│   ├── data/                   # JSON data (master template + filled data)
│   │   ├── master.json         # Base template structure
│   │   └── master_filled.json  # Generated data (output of pipeline)
│   │
│   ├── assets/                 # Generated images (gitignored)
│   ├── temp/                   # Temp PDF pages during generation (gitignored)
│   ├── renderers/              # Page-specific rendering helpers
│   ├── care_lables/            # Care label reference assets
│   ├── .env.example            # API key template
│   └── requirements.txt        # Python dependencies
│
└── proposal.md                 # Project proposal document
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- System libraries for WeasyPrint: `brew install pango gdk-pixbuf libffi` (macOS)

### Backend

```bash
cd swanky_women

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your actual API keys

# Create required directories
mkdir -p assets temp
```

### Frontend

```bash
cd frontend/PCJ-frontend

npm install
npm run dev
```

## Usage

### Generate a Tech Pack (CLI)

```bash
cd swanky_women

# Set library path for WeasyPrint (macOS)
export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib"

# Run the pipeline
python main.py
```

Edit the context in `main.py` `__main__` block to set:
- Input images (front/back garment photos in `assets/`)
- Brand, collection, season
- Fabric preference, size range

The pipeline will:
1. Run all AI agents (classification, color, fabric, construction, measurements, etc.)
2. Generate images (technical sketch, labels)
3. Populate `data/master_filled.json`
4. Render 9 HTML templates to PDF
5. Merge into `Tech_Pack.pdf`

### Generate PDF Only (from existing data)

```bash
cd swanky_women
export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib"

python -c "from generate import generatePdf; generatePdf()"
```

### Run API Server

```bash
cd swanky_women
uvicorn app:app --reload --port 8000
```

## AI Agent Pipeline

The pipeline consists of 9+ specialized agents, each producing structured output:

| Agent | Input | Output | Model |
|-------|-------|--------|-------|
| Header | Context text | Style code, metadata | Pydantic: `TechPackHeader` |
| Color | Garment images | Dominant color, Pantone TCX, palette | Pydantic: `GarmentColorList` |
| Vision | Garment images | Raw observation text | Claude Vision |
| Classification | Vision output | Category, complexity, fit type | Pydantic: `GarmentClassificationModel` |
| Fabric Decision | Classification + context | Composition, GSM, drape, finish | Pydantic: `FabricDecisionModel` |
| Construction | Classification + fabric | Seam specs, stitch types | Pydantic: `ConstructionDecisionModel` |
| Measurement | Classification + context | POMs, tolerances, size chart | Pydantic: `MeasurementDecisionModel` |
| Resolver | All above | Cross-field verified master data | Reconciliation logic |
| Verifier | Resolved data | Final consistency check | Pydantic: `VerificationResult` |

## PDF Templates

Each page is an independent HTML/CSS file rendered by WeasyPrint. Page size: 1240x840px (landscape A4-ish).

Templates use Jinja2 variables populated from `master_filled.json`. To modify a template's layout, edit the corresponding HTML file in `templates/`.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for LLM agents |
| `OPENROUTER_API_KEY` | Yes | OpenRouter key for image generation (Gemini) |

## API Costs

Each tech pack generation consumes:
- ~10-15 Claude API calls (text + vision)
- ~3-5 image generation calls (technical sketch, labels, care label)
- Estimated cost: **$3-8 per tech pack**

## Known Considerations

- WeasyPrint requires system-level libraries (pango, gdk-pixbuf). On macOS, set `DYLD_FALLBACK_LIBRARY_PATH` before running.
- Image generation quality varies per run. Technical sketches may occasionally need regeneration.
- Pantone TCX matching is approximate (nearest-neighbor in LAB color space), not from a licensed Pantone database.
- The `generate=True` flag in `main.py` triggers full AI generation. Set to `False` to re-render PDF from cached data only.
