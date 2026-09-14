import json
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
    "page_1": "intro_page.html",
    "page_2": "3d_cad_design_page.html",
    "page_3": "technical_sketch_page.html",
    "page_4": "accessories_page.html",
    "page_5": "product_construction.html",
    "page_6": "measurements.html",
    "page_7": "fabrics_quality_standards.html",
    "page_8": "size_chart_page.html",
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
            return f"http://localhost:8000/{asset_path}"
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


def _run_generation_job(job_id: str, image_paths: list, context: str):
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
        pdf_path = generate_techpack(image_paths, context, True, progress_callback=progress_callback)

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
        _push_reasoning(job_id, "Complete", "Tech Pack generated", "All 9 pages rendered and merged into PDF.", 100)

    except Exception as e:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(e)
        _jobs[job_id]["current_step"] = f"Error: {str(e)[:120]}"
        print(f"[Generation Job {job_id}] ERROR: {e}")


@app.post("/api/generate")
async def start_generation(
    images: list[UploadFile] = File(...),
    context: str = Form(...),
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
        args=(job_id, saved_paths, context),
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
    })


@app.get("/api/download-pdf")
def download_pdf():
    """Serve the generated Tech_Pack.pdf for download."""
    pdf_path = BASE_DIR / "Tech_Pack.pdf"
    if not pdf_path.exists():
        return JSONResponse({"error": "PDF not found. Generate a tech pack first."}, status_code=404)
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename="Tech_Pack.pdf",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "editor_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
