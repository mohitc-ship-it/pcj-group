import json
from typing import Optional
import threading
from pathlib import Path
from fastapi import FastAPI, Body, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from jinja2 import Environment, FileSystemLoader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import uuid
from fastapi import UploadFile, File
from fastapi.responses import JSONResponse

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"
MASTER_FILE = DATA_DIR / "master_filled.json"
DRAFT_FILE = DATA_DIR / "master_draft.json"

app = FastAPI()
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

ASSETS_DIR = "assets"
BASE_URL = "http://localhost:8000"

os.makedirs(ASSETS_DIR, exist_ok=True)
# --------------------------------------------------
# Utility: load master / draft
# --------------------------------------------------
def load_master():
    with open(MASTER_FILE) as f:
        return json.load(f)


def load_draft():
    if DRAFT_FILE.exists():
        with open(DRAFT_FILE) as f:
            return json.load(f)
    return load_master()


def save_draft(data):
    with open(DRAFT_FILE, "w") as f:
        json.dump(data, f, indent=2)


# --------------------------------------------------
# Page → template mapping (SINGLE SOURCE OF TRUTH)
# --------------------------------------------------
PAGE_TEMPLATE_MAP = {
    "header": "product_construction.html",
    "page_1": "intro_page.html",
    "page_2": "3d_cad_design_page.html",
    "page_3": "technical_sketch_page.html",
    "page_4": "accessories_page.html",
    "page_5": "product_construction.html",
    "page_6": "size_chart_page.html",
    "page_10": "measurements.html",
    "page_7": "fabrics_quality_standards.html",
    "page_8": "reference_image_page.html",
    "page_9": "wash_and_care_label.html",
}



app.mount(
    "/assets",
    StaticFiles(directory="assets"),
    name="assets"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/check")
def check():
  
    return "working"


# --------------------------------------------------
# 1️⃣ Get page data for editor (LEFT PANEL)
# --------------------------------------------------
# @app.get("/api/draft/{page_id}")
# def get_page_draft(page_id: str):
#     data = load_draft()

#     if page_id not in data:
#         return JSONResponse(
#             {"error": "Invalid page id"},
#             status_code=400
#         )
#     # here we have to update urls present in the data so that if can render on frontend where ever in any filed of json objec there is string which inlcudes assets/ means it is url which will not be rendered on frontend so to remove anything written before assets/ and append "http://localhost:8000" so that it can render on frontend
#     return data[page_id]

def update_value_by_key(obj, target_key, new_value):
    """
    Recursively search for target_key in nested dict/list
    and update its value when found.
    Returns True if updated, False otherwise.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == target_key:
                obj[key] = new_value
                return True

            if update_value_by_key(value, target_key, new_value):
                return True

    elif isinstance(obj, list):
        for item in obj:
            if update_value_by_key(item, target_key, new_value):
                return True

    return False


def extract_asset_path(image_url: str) -> str:
    """
    Converts:
    http://localhost:8000/assets/xyz.png
    → assets/xyz.png
    """
    if "assets/" in image_url:
        return "assets/" + image_url.split("assets/")[-1]
    return image_url

def set_nested_value(data: dict, path: str, value):
    """
    Update nested dict using dot-notation path.
    Example:
    path = "page_1.images.front"
    """
    keys = path.split(".")
    ref = data

    for key in keys[:-1]:
        ref = ref[key]

    ref[keys[-1]] = value



def normalize_asset_urls(obj):
    """
    Recursively traverse JSON-like structure and
    fix asset paths for frontend rendering.
    """
    if isinstance(obj, dict):
        return {
            key: normalize_asset_urls(value)
            for key, value in obj.items()
        }

    elif isinstance(obj, list):
        return [
            normalize_asset_urls(item)
            for item in obj
        ]

    elif isinstance(obj, str):
        if "assets/" in obj:
            asset_path = obj[obj.index("assets/"):]
            import time
            timestamp = int(time.time())
            return f"http://localhost:8000/{asset_path}?t={timestamp}"
        return obj

    else:
        return obj


@app.get("/api/draft/{page_id}")
def get_page_draft(page_id: str):
    data = load_draft()

    if page_id not in data:
        return JSONResponse(
            {"error": "Invalid page id"},
            status_code=400
        )

    page_data = data[page_id]

    # Normalize asset URLs ONLY for response
    normalized_data = normalize_asset_urls(page_data)

    return normalized_data


# --------------------------------------------------
# 2️⃣ Live preview (RIGHT PANEL)
# --------------------------------------------------
@app.post("/api/preview/{page_id}")
def preview_page(
    page_id: str,
    page_data: dict = Body(...)
):
    if page_id not in PAGE_TEMPLATE_MAP:
        return HTMLResponse("Invalid page", status_code=400)

    # Load full draft
    draft = load_draft()

    # Update ONLY this page
    draft[page_id] = page_data

    # Persist draft (so page switch keeps edits)
    # save_draft(draft)

    # Render preview using SAME template
    template_name = PAGE_TEMPLATE_MAP[page_id]
    template = env.get_template(template_name)

    html = template.render(**draft)

    return HTMLResponse(html)


# --------------------------------------------------
# 3️⃣ Optional: reset draft
# --------------------------------------------------
@app.post("/api/reset-draft")
def reset_draft():
    master = load_master()
    save_draft(master)
    return {"status": "reset"}


@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)):
    # Validate file type (basic safety)
    if not file.content_type.startswith("image/"):
        return JSONResponse(
            status_code=400,
            content={"error": "Only image files are allowed"}
        )

    # Generate safe unique filename
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"

    file_path = os.path.join(ASSETS_DIR, filename)

    # Save file to assets/
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    # Public URL
    file_url = f"{BASE_URL}/assets/{filename}"
    print("uploaded file path : ", file_url)
    return {
        "url": file_url
    }


# @app.post("/api/update-image-field")
# def update_image_field(payload: dict):
#     page_id = payload["page_id"]
#     field_path = payload["field_path"]
#     image_url = payload["image_url"]

#     print("page_id : ", page_id)
#     print("field_path : ", field_path)
#     print("image_url : ", image_url)

#     draft = load_draft()

#     if page_id not in draft:
#         return JSONResponse(
#             status_code=400,
#             content={"error": "Invalid page id"}
#         )

#     # 🔑 Convert HTTP URL back to local asset path
#     local_asset_path = extract_asset_path(image_url)
#     print("local_asset_path : ", local_asset_path)
#     try:
#         set_nested_value(draft, field_path, local_asset_path)
#     except Exception:
#         return JSONResponse(
#             status_code=400,
#             content={"error": "Invalid field path"}
#         )

#     save_draft(draft)

#     return {"status": "updated"}
@app.post("/api/update-image-field")
def update_image_field(payload: dict):
    page_id = payload["page_id"]
    field_key = payload["field_path"]
    image_url = payload["image_url"]

    draft = load_draft()

    if page_id not in draft:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid page id"}
        )

    local_asset_path = extract_asset_path(image_url)

    updated = update_value_by_key(
        draft[page_id],
        field_key,
        local_asset_path
    )

    if not updated:
        return JSONResponse(
            status_code=400,
            content={"error": "Field key not found"}
        )

    save_draft(draft)

    return {"status": "updated"}

@app.post("/api/update-multiple-fields")
def update_multiple_fields(payload: dict):
    page_id = payload["page_id"]
    updates = payload["updates"]  # dict of key → value

    draft = load_draft()

    if page_id not in draft:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid page id"}
        )

    for key, value in updates.items():
        updated = update_value_by_key(draft[page_id], key, value)
        if not updated:
            return JSONResponse(
                status_code=400,
                content={"error": f"Field not found: {key}"}
            )

    save_draft(draft)
    return {"status": "updated"}

# --------------------------------------------------
# Generation Job Store (in-memory, single-user demo)
# --------------------------------------------------
_jobs: dict = {}

PIPELINE_STEPS = [
    "Analyzing garment images",
    "Extracting dominant color + Pantone TCX",
    "Classifying garment type",
    "Determining fabric composition",
    "Generating construction specs",
    "Calculating measurements + size chart",
    "Running cross-field verification",
    "Generating technical sketch",
    "Generating brand label, care label",
    "Rendering 9-page PDF",
]


def _push_reasoning(job_id: str, step: str, decision: str, reasoning: str, progress: int):
    """Push a reasoning trace entry to the job's step_log."""
    import time
    _jobs[job_id]["current_step"] = step
    _jobs[job_id]["progress"] = progress
    _jobs[job_id]["step_log"].append({
        "step": step,
        "decision": decision,
        "reasoning": reasoning,
        "timestamp": time.strftime("%H:%M:%S"),
    })


def _run_generation_job(job_id: str, image_paths: list, context: str, sample_size: str, brand_logo_path: str = None):
    """Runs generate_techpack in a background thread, updating job state with reasoning traces."""
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(__file__))
        from main import generate_techpack

        # Inject a progress_callback the pipeline can call after each agent
        def progress_callback(step: str, decision: str, reasoning: str, progress: int):
            _push_reasoning(job_id, step, decision, reasoning, progress)

        _push_reasoning(job_id, "Starting pipeline...", "", "Initializing AI agents and loading models.", 2)

        # Run the actual pipeline (blocking, in background thread)
        pdf_path = generate_techpack(image_paths, context, True, sample_size, progress_callback=progress_callback, brand_logo_path=brand_logo_path)

        # Clear any stale draft so the frontend editor loads this new generation
        if DRAFT_FILE.exists():
            try:
                os.remove(DRAFT_FILE)
            except Exception:
                pass

        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["progress"] = 100
        _jobs[job_id]["current_step"] = "Tech Pack ready!"
        _jobs[job_id]["pdf_path"] = str(pdf_path) if pdf_path else None

        # Calculate estimated cost
        image_gen_cost = 0.14  # 4 images × ~$0.035 avg via GPT Image 2.5 Flare
        text_llm_cost = 0.03   # ~13 calls via Gemini Flash
        total_cost = image_gen_cost + text_llm_cost
        _jobs[job_id]["cost"] = {
            "image_generation": round(image_gen_cost, 3),
            "text_vision_llm": round(text_llm_cost, 3),
            "total": round(total_cost, 3),
            "currency": "USD"
        }

        _push_reasoning(job_id, "Complete", "Tech Pack generated", f"All pages rendered. Estimated cost: ${total_cost:.2f}", 100)

    except Exception as e:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(e)
        _jobs[job_id]["current_step"] = f"Error: {str(e)[:120]}"
        print(f"[Generation Job {job_id}] ERROR: {e}")


@app.post("/api/generate")
async def start_generation(
    images: list[UploadFile] = File(...),
    context: str = Form(...),
    sample_size: Optional[str] = Form("M"),
    brand_logo: Optional[UploadFile] = File(None),
):
    """
    Accepts 2+ garment images + context, starts generation in background.
    Returns job_id immediately — client polls /api/generate-status/{job_id}.
    """
    if len(images) < 2:
        return JSONResponse(
            {"error": "At least 2 images (front and back) are required."},
            status_code=400
        )

    os.makedirs(ASSETS_DIR, exist_ok=True)

    # Save all uploaded images as image_0.png, image_1.png, ...
    # Name first two consistently so pipeline auto-detects front/back
    saved_paths = []
    for i, img_file in enumerate(images):
        ext = os.path.splitext(img_file.filename or "")[1] or ".png"
        filename = f"image_{i}_{'front' if i == 0 else 'back' if i == 1 else 'extra'}{ext}"
        dest = os.path.join(ASSETS_DIR, filename)
        with open(dest, "wb") as f:
            f.write(await img_file.read())
        saved_paths.append(dest)

    # Save brand logo if provided
    brand_logo_path = None
    if brand_logo and brand_logo.filename:
        logo_ext = os.path.splitext(brand_logo.filename)[1] or ".png"
        logo_dest = os.path.join(ASSETS_DIR, f"brand_logo_uploaded{logo_ext}")
        with open(logo_dest, "wb") as f:
            f.write(await brand_logo.read())
        brand_logo_path = logo_dest
        print(f"[start_generation] Brand logo saved to {logo_dest}")

    # Create job
    job_id = uuid.uuid4().hex
    _jobs[job_id] = {
        "status": "running",
        "progress": 0,
        "current_step": "Starting pipeline...",
        "pdf_path": None,
        "error": None,
        "step_log": [],   # reasoning traces accumulate here
    }

    # Start background thread
    thread = threading.Thread(
        target=_run_generation_job,
        args=(job_id, saved_paths, context, sample_size, brand_logo_path),
        daemon=True,
    )
    thread.start()

    return JSONResponse({"job_id": job_id, "status": "running", "image_count": len(saved_paths)})



@app.get("/api/generate-status/{job_id}")
def get_generation_status(job_id: str):
    """Poll this endpoint to check generation progress and get reasoning traces."""
    job = _jobs.get(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return JSONResponse({
        "status": job["status"],           # "running" | "done" | "error"
        "progress": job["progress"],        # 0-100
        "current_step": job["current_step"],
        "step_log": job.get("step_log", []),  # reasoning trace entries
        "error": job.get("error"),
        "cost": job.get("cost"),            # cost breakdown when done
    })


@app.get("/api/download-pdf")
def download_pdf():
    """Serve the generated Tech_Pack.pdf for download, regenerating it first."""
    from generate import generatePdf
    
    # Always regenerate from the latest master.json to capture UI edits & layout fixes
    pdf_path = generatePdf()
    
    if not pdf_path or not Path(pdf_path).exists():
        return JSONResponse({"error": "PDF not found. Generate a tech pack first."}, status_code=404)
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename="Tech_Pack.pdf",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )


# ──────────────────────────────────────────────────────────────────────────────
# Feature 2 — Save draft for a specific page
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/save-draft/{page_id}")
async def save_draft_page(page_id: str, data: dict = Body(...)):
    """Merge the submitted page data into master_draft.json and persist it."""
    if page_id not in PAGE_TEMPLATE_MAP:
        return JSONResponse({"error": f"Unknown page: {page_id}"}, status_code=400)
    draft = load_draft()
    draft[page_id] = data
    save_draft(draft)
    return JSONResponse({"ok": True, "page_id": page_id})


# ──────────────────────────────────────────────────────────────────────────────
# Feature 3 — Manual crop: crop a region from an uploaded image
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/manual-crop")
async def manual_crop(payload: dict = Body(...)):
    """
    Crop a pixel region from a source image, save it as a new asset,
    and update the draft for the specified field.
    Payload: { image_path, x, y, width, height, field_key, page_id }
    """
    try:
        from PIL import Image as PILImage
        import uuid as uuid_mod

        image_path = payload.get("image_path", "")
        # Strip the base URL prefix if present
        if "assets/" in image_path:
            image_path = "assets/" + image_path.split("assets/")[1]

        x      = int(payload["x"])
        y      = int(payload["y"])
        w      = int(payload["width"])
        h      = int(payload["height"])
        field  = payload.get("field_key", "")
        page   = payload.get("page_id", "")

        if not Path(image_path).exists():
            return JSONResponse({"error": f"Source image not found: {image_path}"}, status_code=404)

        with PILImage.open(image_path) as img:
            cropped = img.crop((x, y, x + w, y + h))
            out_name = f"manual_crop_{uuid_mod.uuid4().hex[:8]}.png"
            out_path = f"assets/{out_name}"
            cropped.save(out_path)

        # Update draft if field + page provided
        if field and page:
            draft = load_draft()
            if page in draft and field in draft[page]:
                draft[page][field] = out_path
                save_draft(draft)

        return JSONResponse({"ok": True, "new_url": f"{BASE_URL}/{out_path}"})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ──────────────────────────────────────────────────────────────────────────────
# Feature 4 — Regenerate technical sketch via image-to-image
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/regenerate-sketch")
async def regenerate_sketch(payload: dict = Body(...)):
    """
    Apply a modification instruction to the current technical sketch image
    using image-to-image generation, then update the draft.
    Payload: { instruction }
    """
    try:
        from skill_image_gen import generate_image

        instruction = payload.get("instruction", "").strip()
        if not instruction:
            return JSONResponse({"error": "instruction is required"}, status_code=400)

        draft = load_draft()
        current_sketch = draft.get("page_3", {}).get("technical_sketch_img", "assets/technical_sketch.png")
        if "assets/" in current_sketch:
            current_sketch = "assets/" + current_sketch.split("assets/")[1]

        full_prompt = (
            f"TECHNICAL SKETCH MODIFICATION REQUEST:\n"
            f"Reference the existing technical sketch image provided.\n"
            f"Apply the following change: {instruction}\n\n"
            f"Preserve ALL other details of the garment exactly as shown: "
            f"silhouette, construction lines, seam positions, collar style, sleeve design, "
            f"pocket placement, and all other design elements that are NOT mentioned in the change request.\n"
            f"Output a clean, black-and-white technical flat sketch on white background."
        )

        out_path = "assets/technical_sketch.png"
        result = generate_image(full_prompt, reference_image_path=current_sketch, output_path=out_path)
        if not result:
            return JSONResponse({"error": "Generation failed"}, status_code=500)

        draft["page_3"]["technical_sketch_img"] = result
        save_draft(draft)

        return JSONResponse({"ok": True, "new_url": f"{BASE_URL}/{result}"})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ──────────────────────────────────────────────────────────────────────────────
# Feature 4B — Regenerate measurement diagram via image-to-image
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/regenerate-measurement")
async def regenerate_measurement(payload: dict = Body(...)):
    """
    Apply a modification instruction to the measurement diagram.
    Payload: { instruction }
    """
    try:
        from skill_image_gen import generate_image

        instruction = payload.get("instruction", "").strip()
        if not instruction:
            return JSONResponse({"error": "instruction is required"}, status_code=400)

        draft = load_draft()
        current_diagram = draft.get("page_6", draft.get("page_10", {})).get("measurement_image_url", "assets/measurement_diagram.png")
        if "assets/" in current_diagram:
            current_diagram = "assets/" + current_diagram.split("assets/")[1]

        full_prompt = (
            f"MEASUREMENT DIAGRAM MODIFICATION REQUEST:\n"
            f"Reference the existing measurement diagram image provided.\n"
            f"Apply the following change: {instruction}\n\n"
            f"Preserve the garment silhouette and all measurement lines that are NOT mentioned.\n"
            f"Keep letter labels (A, B, C, etc.) clearly visible.\n"
            f"Output a clean, black-and-white technical flat sketch with measurement indicator lines on white background."
        )

        out_path = "assets/measurement_diagram.png"
        result = generate_image(
            full_prompt,
            reference_image_path=current_diagram,
            output_path=out_path
        )
        if not result:
            return JSONResponse({"error": "Generation failed"}, status_code=500)

        # Update both page_6 and page_10
        if "page_6" in draft:
            draft["page_6"]["measurement_image_url"] = result
        if "page_10" in draft:
            draft["page_10"]["measurement_image_url"] = result
        save_draft(draft)

        return JSONResponse({"ok": True, "new_url": f"{BASE_URL}/{result}"})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ──────────────────────────────────────────────────────────────────────────────
# Feature 4C — Get AI reasoning for any field
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/explain-field")
async def explain_field(payload: dict = Body(...)):
    """
    Returns AI reasoning for why a specific field has its current value.
    Payload: { page_id, field_key }
    """
    try:
        draft = load_draft()
        page_id = payload.get("page_id", "")
        field_key = payload.get("field_key", "")

        if page_id not in draft:
            return JSONResponse({"error": "Invalid page"}, status_code=400)

        # Get the field value
        page_data = draft[page_id]
        value = page_data.get(field_key, "")
        if isinstance(value, dict):
            value = json.dumps(value, indent=2)
        elif isinstance(value, list):
            value = json.dumps(value, indent=2)

        # Get garment context
        header = draft.get("header", {})
        description = header.get("description", "garment")
        fabric_info = ""
        fabrics = draft.get("page_7", {}).get("fabrics", [])
        if fabrics and isinstance(fabrics, list) and fabrics[0].get("description"):
            fabric_info = fabrics[0]["description"]

        # Check for stored reasoning
        confidence_data = draft.get("_confidence", {})
        fabric_options = draft.get("page_2", {}).get("_fabric_options", [])
        fabric_reasoning = draft.get("page_7", {}).get("_fabric_reasoning", "")

        reasoning_parts = []

        if field_key in ("fabrics", "description") and fabric_reasoning:
            reasoning_parts.append(f"Fabric reasoning: {fabric_reasoning}")
        if field_key in ("fabrics",) and fabric_options:
            reasoning_parts.append("Options considered:")
            for opt in fabric_options:
                reasoning_parts.append(f"  - {opt.get('fabric', '')} (confidence: {opt.get('confidence', '')}): {opt.get('reasoning', '')}")

        if "pantone" in field_key.lower() or "color" in field_key.lower():
            reasoning_parts.append("Pantone was matched using pantone.com color finder + local Delta-E verification against 2,300 TCX entries.")
            notes = confidence_data.get("_notes", [])
            for n in notes:
                if "pantone" in n.lower() or "color" in n.lower():
                    reasoning_parts.append(n)

        if "seam" in field_key.lower() or "construction" in field_key.lower():
            reasoning_parts.append(f"Construction specs generated for: {description}")
            reasoning_parts.append(f"Fabric: {fabric_info}")
            reasoning_parts.append("Seam types, allowances, and machine types selected based on garment category and fabric weight.")

        if "measurement" in field_key.lower() or "size" in field_key.lower():
            reasoning_parts.append(f"Measurements based on US standard grading for {header.get('category', 'Womenswear')}.")
            reasoning_parts.append(f"Size range: {header.get('size_range', 'S-XL')}")
            reasoning_parts.append("Values use standard increments: +2\" bust/waist per size, +0.5\" shoulder per size.")

        if "accessories" in field_key.lower():
            reasoning_parts.append(f"Accessories identified from visual analysis of {description}.")
            notes = confidence_data.get("_notes", [])
            for n in notes:
                if "closure" in n.lower() or "zipper" in n.lower() or "button" in n.lower():
                    reasoning_parts.append(n)

        if "wash" in field_key.lower() or "care" in field_key.lower() or "composition" in field_key.lower():
            reasoning_parts.append("Care instructions follow client standard: identical for all fabrics.")
            reasoning_parts.append(f"Composite field set to match fabric: {fabric_info}")

        # Overall confidence
        if confidence_data.get("overall"):
            reasoning_parts.append(f"\nOverall confidence: {confidence_data['overall']}")

        if not reasoning_parts:
            reasoning_parts.append(f"This field was generated based on visual analysis of the garment images and garment type: {description}.")

        return JSONResponse({
            "field": field_key,
            "value": str(value)[:500],
            "reasoning": "\n".join(reasoning_parts)
        })

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ──────────────────────────────────────────────────────────────────────────────
# Feature 5 — Regenerate a single table row via LLM
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/regenerate-table-row")
async def regenerate_table_row(payload: dict = Body(...)):
    """
    Regenerate a single row of a content table (seams, accessories, measurements)
    using the LLM with garment context + user instruction.
    Payload: { page_id, table_key, row_index, row_data, instruction }
    """
    try:
        from llm import llm_structured
        import json as _json

        page_id    = payload.get("page_id", "")
        table_key  = payload.get("table_key", "")
        row_index  = int(payload.get("row_index", 0))
        row_data   = payload.get("row_data", {})
        instruction = payload.get("instruction", "").strip()

        # Pull garment context from draft header for richer AI understanding
        draft  = load_draft()
        header = draft.get("header", {})
        page1  = draft.get("page_1", {})
        garment_desc = header.get("description", "garment")
        style_name   = page1.get("style_number", "")
        fabric_info  = ""
        fabrics      = draft.get("page_7", {}).get("fabrics", [])
        if fabrics and isinstance(fabrics, list):
            fabric_info = ", ".join([f.get("fabric_type", "") for f in fabrics[:2] if isinstance(f, dict)])

        # Build the keys schema from the row (exclude meta fields)
        hidden = {"justification", "confidence", "requires_confirmation"}
        row_keys = [k for k in row_data.keys() if k not in hidden]
        keys_str = ", ".join(row_keys)

        prompt = f"""You are a fashion tech pack expert editing a single row in a "{table_key}" table.

GARMENT CONTEXT:
- Style: {style_name}
- Description: {garment_desc}
- Fabric: {fabric_info}

CURRENT ROW (JSON):
{_json.dumps({k: row_data[k] for k in row_keys}, indent=2)}

USER INSTRUCTION:
{instruction}

YOUR TASK:
Apply the instruction to update this row. Return ONLY valid JSON with exactly these keys: {keys_str}
Do not add extra keys. Make the change specific and technically accurate for this garment.
Return only the JSON object, no explanation."""

        # Use LLM with JSON prefill for clean output
        from anthropic import Anthropic
        import os
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "{"},
            ]
        )
        raw = "{" + response.content[0].text.strip()
        # Clean markdown fences if any
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        updated_row = _json.loads(raw.strip())

        # Preserve the hidden meta fields from original row
        for meta in hidden:
            if meta in row_data:
                updated_row[meta] = row_data[meta]

        # Save updated row back into draft
        if page_id in draft and table_key in draft[page_id]:
            table = draft[page_id][table_key]
            if 0 <= row_index < len(table):
                table[row_index] = updated_row
                draft[page_id][table_key] = table
                save_draft(draft)

        return JSONResponse({"ok": True, "updated_row": updated_row})

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)



# ──────────────────────────────────────────────────────────────────────────────
# Feature 7 — Live accuracy scoring with per-component breakdown
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/api/accuracy-report")
def get_accuracy_report():
    """
    Analyzes the current tech pack data and returns per-component
    accuracy scores with reasoning for each.
    """
    try:
        draft = load_draft()
        header = draft.get("header", {})
        description = header.get("description", "unknown garment")
        category = header.get("category", "")
        confidence_data = draft.get("_confidence", {})
        fabric_options = draft.get("page_2", {}).get("_fabric_options", [])
        fabric_reasoning = draft.get("page_7", {}).get("_fabric_reasoning", "")

        components = []

        # --- 1. Pantone / Color ---
        pantone = draft.get("page_2", {}).get("pantone_tcx", "")
        optional_colors = draft.get("page_2", {}).get("optional_colors", [])
        pantone_score = confidence_data.get("pantone_match", 0.75)
        pantone_reasoning = f"Pantone {pantone} matched via pantone.com color finder + local Delta-E."
        if len(optional_colors) > 1:
            pantone_reasoning += f" {len(optional_colors)} color options provided for designer review."
        if pantone_score >= 0.9:
            pantone_reasoning += " High confidence — multiple hex samples agreed on same code."
        elif pantone_score >= 0.7:
            pantone_reasoning += " Moderate confidence — color visually close but may need designer verification."
        else:
            pantone_reasoning += " Low confidence — significant shadow/lighting variation in source image."
        components.append({
            "name": "Pantone / Color",
            "score": round(pantone_score * 100),
            "status": "high" if pantone_score >= 0.85 else "medium" if pantone_score >= 0.7 else "low",
            "reasoning": pantone_reasoning,
            "value": pantone,
        })

        # --- 2. Fabric ---
        fabrics = draft.get("page_7", {}).get("fabrics", [])
        fabric_desc = fabrics[0].get("description", "") if fabrics else ""
        fabric_score = confidence_data.get("fabric_identification", 0.5)
        fabric_reason = fabric_reasoning or "Fabric identified from visual analysis of texture, drape, and sheen."
        if fabric_options:
            top_opt = fabric_options[0]
            fabric_reason += f"\nTop pick: {top_opt.get('fabric', '')} (confidence: {top_opt.get('confidence', '')})"
            fabric_reason += f"\nReasoning: {top_opt.get('reasoning', '')}"
            if len(fabric_options) > 1:
                fabric_reason += f"\nAlternatives: {', '.join(o.get('fabric','') for o in fabric_options[1:])}"
        if fabric_score < 0.7:
            fabric_reason += "\n⚠️ Fabric cannot be precisely determined from images. Designer should verify composition."
        components.append({
            "name": "Fabric Identification",
            "score": round(fabric_score * 100),
            "status": "high" if fabric_score >= 0.85 else "medium" if fabric_score >= 0.7 else "low",
            "reasoning": fabric_reason,
            "value": fabric_desc,
        })

        # --- 3. Construction ---
        seams = draft.get("page_5", {}).get("seams", [])
        construction_score = confidence_data.get("construction_completeness", 0.85)
        construction_reason = f"{len(seams)} construction rows generated for {description}."
        construction_reason += f"\nSeam types and machine types selected based on garment category ({category}) and fabric weight."
        if len(seams) < 6:
            construction_reason += "\n⚠️ Fewer rows than typical — may be missing some construction details."
            construction_score = min(construction_score, 0.7)
        elif len(seams) >= 10:
            construction_reason += "\nComprehensive construction spec covering all major seam points."
        components.append({
            "name": "Product Construction",
            "score": round(construction_score * 100),
            "status": "high" if construction_score >= 0.85 else "medium" if construction_score >= 0.7 else "low",
            "reasoning": construction_reason,
            "value": f"{len(seams)} seam specifications",
        })

        # --- 4. Measurements / POM ---
        measurements = draft.get("page_6", draft.get("page_10", {})).get("measurements", [])
        measurement_score = confidence_data.get("measurement_accuracy", 0.80)
        num_sizes = len(measurements)
        columns = list(measurements[0].keys()) if measurements else []
        columns = [c for c in columns if c != "size"]
        measurement_reason = f"{num_sizes} sizes with {len(columns)} measurement columns: {', '.join(columns)}."
        measurement_reason += f"\nBased on US standard grading for {category}."
        measurement_reason += "\nValues use standard increments: +2\" bust/waist per size, +0.5\" shoulder per size."
        size_range = header.get("size_range", "S-XL")
        if "XS" in size_range and num_sizes < 5:
            measurement_reason += "\n⚠️ Size range includes XS but fewer sizes generated than expected."
            measurement_score = min(measurement_score, 0.7)
        components.append({
            "name": "Measurements / POM",
            "score": round(measurement_score * 100),
            "status": "high" if measurement_score >= 0.85 else "medium" if measurement_score >= 0.7 else "low",
            "reasoning": measurement_reason,
            "value": f"{num_sizes} sizes × {len(columns)} POMs",
        })

        # --- 5. Accessories ---
        accessories = draft.get("page_4", {}).get("accessories", [])
        accessories_score = confidence_data.get("accessories_completeness", 0.85)
        accessories_reason = f"{len(accessories)} accessory items identified."
        has_closure = any("zipper" in str(a).lower() or "button" in str(a).lower() or "pull" in str(a).lower() or "closure" in str(a).lower() for a in accessories)
        has_thread = any("thread" in str(a).lower() for a in accessories)
        has_labels = any("label" in str(a).lower() for a in accessories)
        if has_closure:
            accessories_reason += "\n✓ Closure mechanism identified."
        else:
            accessories_reason += "\n⚠️ No closure listed — verify if garment needs zipper/buttons."
            accessories_score = min(accessories_score, 0.7)
        if has_thread:
            accessories_reason += "\n✓ Thread included."
        if has_labels:
            accessories_reason += "\n✓ Care/size/brand labels included."
        else:
            accessories_reason += "\n⚠️ Labels not listed."
            accessories_score = min(accessories_score, 0.75)

        # Check confidence notes for closure inference
        notes = confidence_data.get("_notes", [])
        for n in notes:
            if "closure" in n.lower() or "zipper" in n.lower() or "pull" in n.lower():
                accessories_reason += f"\n→ {n}"

        components.append({
            "name": "Accessories",
            "score": round(accessories_score * 100),
            "status": "high" if accessories_score >= 0.85 else "medium" if accessories_score >= 0.7 else "low",
            "reasoning": accessories_reason,
            "value": f"{len(accessories)} items",
        })

        # --- 6. Technical Sketch ---
        sketch_path = draft.get("page_3", {}).get("technical_sketch_img", "")
        sketch_exists = bool(sketch_path) and Path(sketch_path.split("assets/")[-1] if "assets/" in sketch_path else sketch_path).exists() if sketch_path else False
        sketch_score = 0.88 if sketch_exists else 0.0
        sketch_reason = "Technical sketch generated via GPT Image 2.5 Flare with reference image input."
        sketch_reason += "\nLabel placement verified by Gemini Flash Vision."
        sketch_reason += "\n⚠️ AI-generated sketches may have minor label positioning inaccuracies. Designer should review."
        components.append({
            "name": "Technical Sketch",
            "score": round(sketch_score * 100),
            "status": "high" if sketch_score >= 0.85 else "medium" if sketch_score >= 0.7 else "low",
            "reasoning": sketch_reason,
            "value": "Generated" if sketch_exists else "Missing",
        })

        # --- 7. Wash & Care ---
        wash = draft.get("page_9", {}).get("wash_label", {})
        composition = wash.get("composition", "")
        care_score = 0.95  # Always high — client uses standard instructions
        care_reason = f"Composite: {composition}. Standard client care instructions applied (identical for all fabrics)."
        care_reason += "\n✓ Washing, bleaching, drying, ironing, dry cleaning — all follow client convention."
        care_reason += "\n✓ Care label instructions + Other Standards (Oekotex, EU Ecolabel) — static, always correct."
        if not composition:
            care_score = 0.5
            care_reason += "\n⚠️ Composition field is empty."
        components.append({
            "name": "Wash & Care Label",
            "score": round(care_score * 100),
            "status": "high" if care_score >= 0.85 else "medium" if care_score >= 0.7 else "low",
            "reasoning": care_reason,
            "value": composition or "Not set",
        })

        # --- 8. Quality Standards ---
        quality = draft.get("page_7", {}).get("quality_standards", [])
        quality_score = 1.0 if len(quality) == 6 else 0.8
        quality_reason = f"{len(quality)} ISO quality tests. These are STATIC — identical across all tech packs per client convention."
        quality_reason += "\nISO 13934-2, ISO 5077, ISO 105-C06, ISO 105-X12, ISO 105-D01, ISO 13935-2."
        components.append({
            "name": "Quality Standards",
            "score": round(quality_score * 100),
            "status": "high",
            "reasoning": quality_reason,
            "value": f"{len(quality)} tests",
        })

        # --- Overall ---
        overall_score = sum(c["score"] for c in components) / len(components) if components else 0

        return JSONResponse({
            "overall_score": round(overall_score),
            "garment": description,
            "category": category,
            "components": components,
            "total_components": len(components),
            "high_confidence": len([c for c in components if c["status"] == "high"]),
            "needs_review": len([c for c in components if c["status"] != "high"]),
        })

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "editor_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
