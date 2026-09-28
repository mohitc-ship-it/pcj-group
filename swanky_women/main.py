import os
import json
import datetime
from copy import deepcopy
from pathlib import Path

from llm import analyze_images, llm_structured, llm_query
from generate import generatePdf
from utils import extract_clothing_palette, map_json, combine_images_horizontally, split_into_grids, recommend_colors_from_images, nearest_pantone_tcx, ai_crop_detail_regions, format_technical_sketch, render_pantone_swatches, cluster_into_color_groups
from imageGen import generate_image
from image_verifier import verify_and_regenerate
from sketch_prompter import build_normal_sketch_prompt, build_json_sketch_prompt, convert_text_to_json_prompt

from models import (
    TechPackHeader,
    GarmentColorModel,
    GarmentStructureModel,
    GarmentClassificationModel,
    FabricDecisionModel,
    ConstructionDecisionModel,
    MeasurementDecisionModel,
    FactoryInstructionModel,
    VerificationResult,
    QualityStandardsList,
    SizeChartList,
    GarmentColorList
)

# =========================================================
# SAFETY HELPERS
# =========================================================

def ensure_page(master, key):
    master.setdefault(key, {})
    print(f"[DEBUG] ensure_page: ensured page key='{key}' present (len now={len(master[key])})")
    return master[key]

def ensure_page_9_contract(page_9: dict) -> dict:
    page_9.setdefault("wash_label", {})
    page_9.setdefault("care_label", {"image": "assets/care_label.png"})
    page_9.setdefault("care_label_instructions", [])
    page_9.setdefault("other_standards", [])
    print(f"[DEBUG] ensure_page_9_contract: keys after ensure -> {list(page_9.keys())}")
    return page_9


# =========================================================
# AGENT 0 — COLOR (SINGLE SOURCE OF TRUTH)
# =========================================================

# def extract_garment_color(images):
#     palette = extract_clothing_palette(images[0])

#     prompt = f"""
#     You are a fashion color expert, designing a tech pack for a garment.

#     Task:
#     - Select the SINGLE main garment color
#     - Ignore shadows, folds, lighting
#     - Suggest closest Pantone TCX (mark as SUGGESTED)

#     Rules:
#     - Do NOT guarantee Pantone accuracy
#     - Output JSON only

#     HEX OPTIONS:
#     {palette}
#     """

#     return llm_structured(
#         analyze_images(images, prompt),
#         GarmentColorModel
#     ).model_dump()

def extract_garment_color(images):
    """
    Extracts the primary garment color(s) from the images.

    If MULTI_PANTONE=true in .env:
        1. Extracts top-5 hex candidates from pixel clustering.
        2. For each hex, scrapes the Pantone website for real TCX matches.
        3. Renders all candidates as a labeled color-swatch grid PNG.
        4. Passes the garment image + swatch grid to Vision AI for visual ranking.
        5. The top-ranked Pantone goes on the slide; all ranked options go to the manual editor.

    Otherwise: runs the existing simple pipeline.
    """
    multi_pantone = os.environ.get("MULTI_PANTONE", "false").strip().lower() == "true"

    # Extract top hex candidates from image pixels (always needed)
    palette = recommend_colors_from_images(images[0], images[1] if len(images) > 1 else images[0])
    print(f"[DEBUG] extract_garment_color: palette length={len(palette)}")

    # ─────────────────────────────────────────────────────────
    # NEW PIPELINE — Vision-grounded Pantone ranking
    # ─────────────────────────────────────────────────────────
    if multi_pantone:
        print("[DEBUG] extract_garment_color: MULTI_PANTONE=true → using vision-grounded pipeline")
        from pantone_scraper import get_tcx_options
        import re, json as _json

        # ─── PHASE 1: Vision Gatekeeper — how many FABRIC colors? ───────────────
        gatekeeper_prompt = """Look at this garment image carefully.

Count how many distinct COLORS are used for the main fabrics and prominent trims.

STRICT RULES:
- DO NOT count: small isolated hardware (buttons, zippers, rivets, buckles, clasps, eyelets).
- DO NOT count: model skin, hair, background, shadows, or lighting effects.
- DO NOT count: labels or tags.
- YES, DO COUNT: Prominent trims, edgings, piping, braiding, or continuous chain details that outline the garment (collar, front opening, cuffs, hem), even if they appear metallic. These are considered secondary textile/trim colors.
- YES, DO COUNT: Large color-blocked fabric areas.

Examples:
- Navy blazer with gold buttons → 1 (buttons are isolated hardware, ignored)
- Navy jacket with gold chain/braid trim outlining the collar, front, and cuffs → 2 (the gold trim is a prominent continuous detail)
- Black and white color-block dress → 2 (both are distinct fabric areas)

Return ONLY a raw JSON object with no explanation:
{"fabric_color_count": 1, "fabric_color_notes": ["Navy main body"]}
or
{"fabric_color_count": 2, "fabric_color_notes": ["Navy main body", "Gold chain trim on collar, cuffs, and hem"]}
"""
        gatekeeper_text, _ = analyze_images(images, gatekeeper_prompt, enable_thinking=False)
        print(f"[DEBUG] MULTI_PANTONE: gatekeeper response: {gatekeeper_text[:200]}")

        fabric_color_count = 1  # safe default
        fabric_color_notes = []
        try:
            m = re.search(r'\{.*?\}', gatekeeper_text, re.DOTALL)
            if m:
                parsed = _json.loads(m.group())
                fabric_color_count = int(parsed.get("fabric_color_count", 1))
                fabric_color_notes = parsed.get("fabric_color_notes", [])
        except Exception as e:
            print(f"[DEBUG] MULTI_PANTONE: gatekeeper parse error: {e}, defaulting to 1 color")

        print(f"[DEBUG] MULTI_PANTONE: gatekeeper → {fabric_color_count} fabric color(s): {fabric_color_notes}")

        # ─── PHASE 2: Helper to run the scrape→swatch→rank pipeline for one color group ─
        def _run_single_color_pipeline(hex_candidates, color_label="primary"):
            """Takes a list of hex strings, scrapes Pantone, ranks, and returns one color result dict."""
            all_scraped = []
            parent_hex_map = {}

            for hex_color in hex_candidates:
                print(f"[DEBUG] MULTI_PANTONE [{color_label}]: scraping website for hex {hex_color}")
                options = get_tcx_options(hex_color)
                for opt in options:
                    code = str(opt.get("code") or opt.get("name", ""))
                    if code and " TCX" not in code:
                        code = f"{code} TCX"
                    if code and code not in parent_hex_map:
                        parent_hex_map[code] = hex_color
                    opt["code"] = code
                all_scraped.extend(options)

            seen_codes = set()
            pantone_pool = []
            for opt in all_scraped:
                code = opt["code"]
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    pantone_pool.append({
                        "code": code,
                        "name": opt.get("name", ""),
                        "hex":  parent_hex_map.get(code, "#888888"),
                    })

            if not pantone_pool:
                print(f"[DEBUG] MULTI_PANTONE [{color_label}]: scraper returned 0 options")
                return None

            print(f"[DEBUG] MULTI_PANTONE [{color_label}]: {len(pantone_pool)} unique Pantone options")

            swatch_path = render_pantone_swatches(pantone_pool)
            print(f"[DEBUG] MULTI_PANTONE [{color_label}]: swatch grid → {swatch_path}")

            comparison_prompt = f"""You are a professional textile color specialist.

You will see:
1. The original garment photo(s) — examine the **{color_label} fabric** color carefully.
2. A grid of labeled Pantone TCX color swatches.

Your task:
Rank the swatches from CLOSEST to FURTHEST match to the **{color_label} fabric** color.
Consider: hue, value (lightness/darkness), and saturation.

Return ONLY a raw JSON array of Pantone codes in ranked order. Example:
["19-3921 TCX", "19-3953 TCX", "19-4024 TCX"]

No explanation. Only the JSON array.
"""
            comparison_images = images + [swatch_path]
            ranked_text, _ = analyze_images(comparison_images, comparison_prompt, enable_thinking=False)
            print(f"[DEBUG] MULTI_PANTONE [{color_label}]: vision ranked: {ranked_text[:200]}")

            ranked_codes = []
            try:
                json_match = re.search(r'\[.*?\]', ranked_text, re.DOTALL)
                if json_match:
                    ranked_codes = _json.loads(json_match.group())
            except Exception as e:
                print(f"[DEBUG] MULTI_PANTONE [{color_label}]: JSON parse error: {e}")

            if not ranked_codes:
                ranked_codes = [p["code"] for p in pantone_pool]

            winner_code = ranked_codes[0]
            winning_parent_hex = parent_hex_map.get(winner_code, hex_candidates[0])
            print(f"[DEBUG] MULTI_PANTONE [{color_label}]: winner = {winner_code} hex={winning_parent_hex}")

            filtered_ranked_codes = [c for c in ranked_codes if parent_hex_map.get(c) == winning_parent_hex]

            code_to_name = {p["code"]: p["name"] for p in pantone_pool}
            code_to_hex  = {p["code"]: p["hex"]  for p in pantone_pool}

            return {
                "color_name":   code_to_name.get(winner_code, ""),
                "color_hex":    winning_parent_hex,
                "pantone_tcx":  winner_code,
                "pantone_options": [
                    {"code": c, "name": code_to_name.get(c, ""), "hex": code_to_hex.get(c, "")}
                    for c in filtered_ranked_codes
                ],
                "pantone_accuracy_note": f"Vision-grounded ranking — parent hex filter ({winning_parent_hex})"
            }

        # ─── PHASE 3: Branch on color count ──────────────────────────────────────
        final_colors = []

        if fabric_color_count == 1:
            # Single-color path: take top 3 hexes from the dominant cluster
            top_3_hex = [c["hex"] for c in palette[:3]]
            result = _run_single_color_pipeline(top_3_hex, color_label="main fabric")
            if result:
                final_colors.append(result)

        else:
            # Multi-color path: split palette into 2 distinct color groups
            color_groups = cluster_into_color_groups(palette, n_groups=2, min_lab_distance=22.0)
            print(f"[DEBUG] MULTI_PANTONE: split into {len(color_groups)} color groups")

            labels = ["primary fabric", "secondary fabric"]
            for i, group in enumerate(color_groups):
                if not group:
                    continue
                # Take top 2 hexes from this group as candidates for the scraper
                group_sorted = sorted(group, key=lambda x: x.get("confidence", 0), reverse=True)
                hex_candidates = [c["hex"] for c in group_sorted[:2]]
                label = labels[i] if i < len(labels) else f"fabric {i+1}"
                result = _run_single_color_pipeline(hex_candidates, color_label=label)
                if result:
                    # Override color_name with the gatekeeper's note if available
                    if i < len(fabric_color_notes):
                        result["color_note"] = fabric_color_notes[i]
                    final_colors.append(result)

        if not final_colors:
            print("[DEBUG] MULTI_PANTONE: all pipelines failed, falling back to simple pipeline")
            multi_pantone = False  # fall through below
        else:
            return {"colors": final_colors}


    # ─────────────────────────────────────────────────────────
    # EXISTING PIPELINE — simple LLM-based extraction
    # ─────────────────────────────────────────────────────────
    palette_with_pantone = []
    for color in palette[:6]:
        tcx_matches = nearest_pantone_tcx(color["hex"], top_k=1)
        best_match  = tcx_matches[0] if tcx_matches else None
        palette_with_pantone.append({
            **color,
            "verified_pantone_code": best_match["code"] if best_match else "N/A",
            "verified_pantone_name": best_match["name"] if best_match else "N/A",
            "delta_e":               best_match["delta_e"] if best_match else None,
        })

    prompt = f"""
ROLE: Textile Color Matching Specialist

You are working for a **fashion brand color lab**.
Your job is to identify the **primary garment colors** from the provided images and palette.

This color will be used in a **factory tech pack**, so accuracy and conservatism are critical.

You are NOT allowed to invent colors.
You must work only from:
• The garment pixels in the images
• The extracted HEX palette provided

────────────────────────────────────────────
INPUTS
────────────────────────────────────────────

GARMENT IMAGES
(Visual reference of the actual garment)

EXTRACTED COLOR PALETTE (from garment pixels)
{palette}

────────────────────────────────────────────
YOUR TASK
────────────────────────────────────────────

You must determine ALL prominent colors on the garment:

1. The **Primary Garment Color** (Main Fabric)
   - The color that covers the **largest surface area** of the garment.

2. Any **Secondary / Trim Colors** (e.g., Piping, Contrast Collar, lining)
   - Colors used for specific FABRIC details.
   - STRICTLY IGNORE colors of buttons, zippers, hardware, metallic trims, and non-textile accessories.
   - Ignore shadows, highlights, and lighting bias.

────────────────────────────────────────────
OUTPUT
────────────────────────────────────────────

Return a JSON list of **GarmentColorModel** containing only the actually present primary and secondary FABRIC colors.
Do not output variations of the same color. Only output distinct functional colors.
"""

    print(f"[DEBUG] extract_garment_color: simple pipeline — calling analyze_images...")
    _analysis, _analysis_think = analyze_images(images, prompt, enable_thinking=True)
    _obj, _think = llm_structured(_analysis, GarmentColorList, enable_thinking=True)
    result = _obj.model_dump()
    print(f"[DEBUG] extract_garment_color: got {len(result.get('colors', []))} colors")
    return result


# =========================================================
# AGENT 1 — VISION (OBSERVE ONLY)
# =========================================================

# def vision_agent(images):
#     prompt = """
#     ROLE: Senior Technical Designer (Vision Only)

#     TASK:
#     Extract ONLY observable garment facts.
    
#     HOW A DESIGNER READS AN IMAGE (Designer Intuition):
#     When a designer sees a dress image, their brain auto-parses:
    
#     A. Silhouette & Fit
#     From the image:
#     - Fitted vs Flowing
#     - Hem definition (asymmetrical, straight, etc.)
#     - Slits, Ruching, Pleats
    
#     B. Garment Type Logic
#     - Category (e.g., Womenswear)
#     - Sub-category (e.g., Dress)
#     - Length (Midi, Maxi)
#     - Complexity (impacts stitch types, seams, QC)

#     OUTPUT:
#     - garment_category
#     - garment_type
#     - length
#     - sleeves
#     - fit_impression
#     - closure_visibility
#     - visible_features
#     - hem_type
#     - complexity
#     - raw_observation_text

#     RULES:
#     - No fabric assumptions
#     - No construction assumptions
#     - No marketing language
#     """

#     vision_text = analyze_images(images, prompt)

#     return {
#         "raw_observation_text": vision_text,
#         "structure": llm_structured(vision_text, GarmentStructureModel).model_dump()
#     }

def vision_agent(images):
    prompt = """
ROLE: Senior Technical Designer (Vision Only)

You are looking at **garment photographs** for the purpose of creating a **factory tech pack**.

You are NOT allowed to imagine, infer, or assume.
You are only allowed to state what can be **directly observed** from the images.

If something is unclear, say:
"Not clearly visible"

────────────────────────────────────────────
WHAT YOU ARE DOING
────────────────────────────────────────────

You must extract **only physical, visible garment facts** — the same way a pattern maker visually inspects a sample.

You are NOT designing.
You are NOT interpreting brand intent.
You are NOT filling missing gaps.

You are **describing what exists.**

────────────────────────────────────────────
DESIGNER VISION FRAMEWORK
────────────────────────────────────────────

When a technical designer looks at a garment image, they see:

A. SILHOUETTE & SHAPE  
• Fitted, semi-fitted, loose, oversized  
• Straight, A-line, flared, tapered  
• Draped vs structured  

B. LENGTH  
• Cropped, hip, waist, knee, midi, maxi, floor  
• Sleeve: sleeveless, short, 3/4, long  

C. GARMENT TYPE
• Coat, Trench Coat, Jacket, Blazer, Outerwear, Dress, Top, Trousers, Skirt, etc
• Womenswear, menswear, unisex  

D. CLOSURES (only if visible)  
• Buttons  
• Zippers  
• Ties  
• None visible  

E. HEM & EDGES  
• Straight / Level (front and back hem lengths are EQUAL)  
• Curved / Shirt-tail  
• Hi-Low / Dropped back hem (back visibly longer than front)  
• Asymmetrical  
• Raw edge  
• Finished edge  
• HEM LENGTH BALANCE DOUBLE-CHECK: For T-shirts, shirts, nightdresses, tops, and dresses, explicitly check whether the Front and Back hem lengths are EQUAL/LEVEL or if the back is longer. Unless an asymmetrical or hi-low drop hem is clearly visible, record the hemline as "Equal/Level length (Front and Back equal)". Never assume the back is longer.

F. PANELING & FEATURES  
• Seams  
• Pleats  
• Darts  
• Ruching  
• Panels  
• Slits  
• Pockets  
• Collars  
• Cuffs  

G. COMPLEXITY  
Based on:
• Number of panels  
• Curved seams  
• Visible closures  
• Layering  

────────────────────────────────────────────
WHAT YOU MUST OUTPUT
────────────────────────────────────────────

You must produce:

• garment_category  
• garment_type  
• length  
• sleeves  
• fit_impression  
• closure_visibility  
• visible_features  
• hem_type (specify hem finish and explicitly state whether front and back lengths are equal/level or hi-low)  
• complexity  
• raw_observation_text  

Each field must be based ONLY on what can be seen.

────────────────────────────────────────────
STRICT RULES
────────────────────────────────────────────

• NO fabric guesses  
• NO construction guesses  
• NO marketing words  
• NO assumptions about inside construction  
• If not visible → "Not visible"  
• If unclear → "Not clear"

You are describing the garment like a factory inspector — not selling it.
"""

    vision_text, _vision_think = analyze_images(images, prompt)
    print(f"[DEBUG] vision_agent: analyze_images returned text length={len(vision_text) if vision_text else 0}")
    _obj, _think = llm_structured(vision_text, GarmentStructureModel, enable_thinking=True)
    structure = _obj.model_dump()
    print(f"[DEBUG] vision_agent: structure keys={list(structure.keys())}")
    return {
        "raw_observation_text": vision_text,
        "structure": structure
    }


# =========================================================
# AGENT 2 — GARMENT CLASSIFICATION
# =========================================================

# def garment_identifier_agent(structure):
#     prompt = f"""
#     ROLE: Garment Classification Agent

#     INPUT:
#     {json.dumps(structure, indent=2)}

#     TASK:
#     Classify garment using the following DECISION TREE (Designer Logic):

#     1. Garment Identification Tree
#     Is the garment for:
#      ├── Womenswear/Menswear/Kidswear
#      │    ├── Category (Dress/Top/Bottom/Outerwear/etc)
#      │    │    ├── Length?
#      │    │    │    ├── Mini / Midi / Maxi / Regular / Cropped
#      │    │    ├── Sleeves?
#      │    │    │    ├── Sleeveless / Short / Long / 3/4
#      │    │    ├── Fit?
#      │    │    │    ├── Body-hugging / Semi-fitted / Relaxed / Oversized
#      │    │    └── Complexity?
#      │    │         ├── Basic
#      │    │         ├── Medium
#      │    │         └── Complex (e.g. slits, ruching, asymmetry)

#     This single decision controls:
#     - Fabric type
#     - Stitch types
#     - Measurement tolerance
#     - QC strictness

#     OUTPUT:
#     - Classification Model (market, category, sub_category, length_type, sleeve_type, fit_type, complexity_level, etc.)
#     """
#     return llm_structured(prompt, GarmentClassificationModel).model_dump()
def garment_identifier_agent(structure):
    prompt = f"""
ROLE: Garment Classification Agent  
You are a **Senior Apparel Technical Designer** responsible for assigning the **official garment identity** used by factories, merchandisers, and QA teams.

You must classify the garment using **only what exists in the provided structure**.

You are NOT allowed to guess gender, length, fit, or complexity.
If information is missing or unclear → mark it as **"Not specified"**.

────────────────────────────────────────────
INPUT — VISUAL & STRUCTURAL DATA
────────────────────────────────────────────
{json.dumps(structure, indent=2)}

This structure was produced by a **vision-only inspection**.  
Treat it as ground truth.

────────────────────────────────────────────
YOUR RESPONSIBILITY
────────────────────────────────────────────

You must determine:

• Market (Womenswear / Menswear / Kidswear / Unisex)  
• Category (Dress, Top, Bottom, Outerwear, etc)  
• Sub-category (e.g. Shirt Dress, T-shirt, Coat, Skirt, etc)  
• Length Type (Mini, Midi, Maxi, Regular, Cropped)  
• Sleeve Type (Sleeveless, Short, 3/4, Long)  
• Fit Type (Body-hugging, Semi-fitted, Relaxed, Oversized)  
• Complexity Level (Basic / Medium / Complex)

This classification controls:
• Fabric selection
• Stitch systems
• Measurement tolerances
• QC strictness
• Costing

────────────────────────────────────────────
DESIGNER DECISION LOGIC
────────────────────────────────────────────

Use only what is visible in structure:

A. MARKET  
Infer only if silhouette or cut clearly indicates:
• Womenswear  
• Menswear  
• Kidswear  
Else → Unisex

B. CATEGORY  
Based on:
• Presence of sleeves
• Presence of waist seam
• Length
• Body coverage
etc

Examples:
• Full body coverage → Dress  
• Upper body only → Top  
• Waist down → Bottom  
• Heavy or layered → Outerwear  

C. SUB-CATEGORY  
Use industry-standard terms derived from shape:
• Shirt dress  
• A-line dress  
• Tunic  
• Blouse  
• Jacket  
• Trousers  
• Skirt  

If unsure → "Generic [Category]"

D. LENGTH  
Use visible hem relative to body:
• Mini  
• Midi  
• Maxi  
• Cropped  
• Regular  

E. SLEEVES  
From structure:
• Sleeveless  
• Short  
• 3/4  
• Long  

F. FIT  
Based on silhouette:
• Body-hugging  
• Semi-fitted  
• Relaxed  
• Oversized  

G. COMPLEXITY  
Based on:
• Number of panels  
• Presence of slits, ruching, asymmetry  
• Visible closures  

• Basic → Straight, minimal seams  
• Medium → Some shaping or closures  
• Complex → Slits, ruching, asymmetry, multiple panels  

────────────────────────────────────────────
STRICT RULES
────────────────────────────────────────────

• Do NOT invent garment type  
• Do NOT assume gender  
• Do NOT infer fabric  
• Do NOT guess hidden structure  
• If not visible → "Not specified"  

You are classifying a real physical sample.

────────────────────────────────────────────
OUTPUT
────────────────────────────────────────────

Return a **GarmentClassificationModel** with:

• market  
• category  
• sub_category  
• length_type  
• sleeve_type  
• fit_type  
• complexity_level  

Every field must be justified by structure.
"""
    print(f"[DEBUG] garment_identifier_agent: structure preview keys={list(structure.keys()) if isinstance(structure, dict) else 'Not dict'}")
    _obj, _think = llm_structured(prompt, GarmentClassificationModel, enable_thinking=True)
    classification = _obj.model_dump()
    print(f"[DEBUG] garment_identifier_agent: classification -> market={classification.get('market')} category={classification.get('category')}")
    return classification


# =========================================================
# AGENT 3 — FABRIC DECISION (PROPERTIES ONLY)
# =========================================================

def fabric_decision_agent(classification, structure, brand_context,garment_color):
    prompt = f"""
ROLE: Fabric Decision Agent

INPUTS:
Classification:
{classification}

Structure:
{structure}

Brand Context (CRITICAL — read carefully for fabric specification):
{brand_context}

Garment primary color: {garment_color}

────────────────────────────────────────────
CRITICAL FABRIC SELECTION RULE
────────────────────────────────────────────

The brand context above may specify ONE or MORE fabric options.

You must SELECT ONE primary fabric — do NOT blend or mix multiple options.

Examples of CORRECT behavior:
- Context says "Fabric: Silk" → fabric_composition = "100% Silk" or "97% Silk / 3% Elastane"
- Context says "Fabric options: Gabardine / Wool blends" → SELECT the most appropriate ONE
- Context says "Fabric: Cotton with stretch" → fabric_composition = "90% Cotton / 10% Spandex"

Examples of WRONG behavior (NEVER do this):
- Context lists "Silk, Cotton, Linen, Wool" → WRONG to output "40% Cotton / 30% Linen / 20% Silk / 10% Wool"
- This is SELECTING from a menu, NOT creating a blend of all options

────────────────────────────────────────────
FABRIC DECISION TREE
────────────────────────────────────────────

Does the garment cling to body?
 ├── Yes → Stretch required
 │    ├── Light stretch → 2–4% elastane
 │    └── High stretch → 5–8% elastane
 └── No → Woven acceptable

Does it flow/drape?
 ├── Yes → Knit / bias cut / soft weave
 └── No → Structured weave

Season?
 ├── Summer → 140–200 GSM
 ├── Fall → 200–260 GSM (Medium weight)
 └── Winter → 260+ GSM (Heavy weight)

OUTPUT:
- FabricDecisionModel
"""
    print(f"[DEBUG] fabric_decision_agent: inputs -> classification keys={list(classification.keys()) if isinstance(classification, dict) else 'N/A'}; garment_color={garment_color.get('hex') if isinstance(garment_color, dict) else garment_color}")
    _obj, _think = llm_structured(prompt, FabricDecisionModel, enable_thinking=True)
    fabric = _obj.model_dump()
    print(f"[DEBUG] fabric_decision_agent: fabric decision keys={list(fabric.keys())}")
    return fabric



    # Designer Logic:
    # - Cotton/Spandex OR Polyester/Elastane often used for stretch.
    # - 2-way stretch for body-hugging + ruching.
    # - Matte surface vs Sheen.
# # =========================================================
# # AGENT 4 — CONSTRUCTION DECISION (NO STITCH CODES)
# # =========================================================

# def construction_decision_agent(classification, fabric_decision, structure):
#     prompt = f"""
#     ROLE: Construction Decision Agent

#     INPUTS:
#     Classification:
#     {classification}

#     Fabric Decision:
#     {fabric_decision}

#     Structure:
#     {structure}

#     TASK:
#     Decide Construction Logic using the DECISION TREE:

#     3. Construction Decision Tree
#     Area under stress?
#      ├── Yes → Overlock / Reinforced seam
#      └── No → Lockstitch

#     Area visible?
#      ├── Yes → Clean finish, tight SPI
#      └── No → Utility finish

#     Stretch area?
#      ├── Yes → Coverstitch / stretch seam
#      └── No → Regular stitch

#     example Designer Logic:
#     - Side seams → Overlock (stretch + strength)
#     - Shoulder seams → Lockstitch (clean, stable)
#     - Hem → Coverstitch (stretch + clean finish)
#     - Zipper → Invisible zipper foot

#     OUTPUT:
#     - ConstructionDecisionModel (seam_decisions, overall_complexity, risk_areas, etc.)
#     DO NOT specify factory stitch codes yet (e.g. 301, 504) - focus on STRATEGY.
#     """
#     return llm_structured(prompt, ConstructionDecisionModel,model="gpt-5.2").model_dump()

def construction_decision_agent(classification, fabric_decision, structure):
    # Load the external seam knowledge base for richer, more accurate seam decisions
    _kb_path = Path(__file__).resolve().parent / "data" / "seam_knowledge_base.md"
    seam_kb = _kb_path.read_text(encoding="utf-8") if _kb_path.exists() else "(seam knowledge base not found)"

    prompt = f"""
ROLE: Construction Decision Agent  
You are a **Senior Apparel Technical Designer & Factory Process Engineer**.  
Your responsibility is to convert garment intent into **correct seam strategy, construction logic, and risk-aware assembly planning** — before any factory machine codes are chosen.

You DO NOT invent design elements.  
You ONLY work from what is explicitly visible or already derived in:
• Classification  
• Fabric Decision  
• Structure  

If something is not present, you mark it as **not applicable**.

────────────────────────────────────────────
INPUTS
────────────────────────────────────────────

GARMENT CLASSIFICATION  
{classification}

FABRIC & MATERIAL BEHAVIOR  
{fabric_decision}

GARMENT STRUCTURE (PANELS + COMPONENTS)  
{structure}

────────────────────────────────────────────
YOUR JOB
────────────────────────────────────────────

You must determine:

1. **How every seam should be constructed**
2. **Which areas require reinforcement**
3. **Which areas require clean finishing**
4. **Which areas must accommodate stretch**
5. **Which areas create production risk**
6. **Overall construction difficulty**

This is NOT about specific machine codes (301, 504, etc).  
This is about **seam strategy and assembly logic**.

────────────────────────────────────────────
CONSTRUCTION DECISION FRAMEWORK
────────────────────────────────────────────

For EVERY seam or joining point, you must evaluate:

────────────────────────────
A. STRESS ANALYSIS
────────────────────────────
Does this area experience pulling, weight, or motion?

Examples:
• Armhole
• Shoulder
• Side seam
• Crotch
• Waist
• Zipper base
• Pocket opening

IF YES → seam must be reinforced or flexible  
IF NO → seam can be lighter and cleaner

────────────────────────────
B. VISIBILITY
────────────────────────────
Is this seam visible to the customer when worn?

Examples:
• Side seam on fitted garments → Visible
• Center back seam → Often visible
• Inside lining seam → Not visible

IF VISIBLE → prioritize clean edge, tight stitching, symmetry  
IF NOT VISIBLE → prioritize strength and speed

────────────────────────────
C. STRETCH REQUIREMENT
────────────────────────────
Based on fabric + placement:
• Knit?
• Spandex?
• Bias cut?
• High movement zone?

IF YES → must allow fabric to stretch without thread break  
IF NO → standard seam behavior is fine

────────────────────────────
D. FABRIC RISK
────────────────────────────
From Fabric Decision:
• Is fabric sheer?
• Is it heavy?
• Is it slippery?
• Is it fraying?
• Is it stiff?

This affects:
• Seam bulk
• Edge finishing
• Puckering risk
• Needle stress
• Thread break risk

────────────────────────────────────────────
DESIGNER-LEVEL DEFAULT LOGIC
────────────────────────────────────────────

Use these as baseline rules UNLESS structure or fabric overrides them:

• Shoulder seams  
  → Stable, non-stretch seam, clean appearance

• Side seams  
  → Must tolerate body movement, medium-high stress

• Armholes  
  → High stress + movement → flexible + reinforced

• Hem  
  → Must allow garment movement + clean finish

• Zipper seams  
  → Must be flat, precise, and stable

• Waist seams  
  → Load-bearing → reinforced or stabilized

• Pocket openings  
  → Stress points → reinforced

• Decorative seams  
  → Clean finish prioritized

────────────────────────────────────────────
WHAT YOU MUST PRODUCE
────────────────────────────────────────────

You must return a **ConstructionDecisionModel** containing:

1. `seam_decisions`
   For each major seam (side, shoulder, hem, armhole, zipper, waist, panels):
   - seam_strategy (reinforced, clean, stretch-tolerant, utility, hidden, etc)
   - reasoning (why this seam requires this strategy)
   - visibility (visible / semi-visible / hidden)
   - stress_level (low / medium / high)
   - stretch_required (yes / no)

2. `risk_areas`
   List all areas that have:
   - High stress
   - Fabric sensitivity
   - Precision requirements
   - Puckering or distortion risk

3. `overall_complexity`
   One of:
   - low
   - medium
   - high  
   Based on:
   • Number of panels  
   • Fabric difficulty  
   • Precision seams (zippers, curved seams, hems, etc)

4. `construction_notes`
   High-level factory instructions such as:
   - “Requires careful handling due to slippery fabric”
   - “High precision required at zipper insertion”
   - “Multiple curved seams increase sewing difficulty”

────────────────────────────────────────────
SEAM KNOWLEDGE BASE (USE THIS AS YOUR REFERENCE)
────────────────────────────────────────────

The following is a professional garment construction seam reference document.
You MUST use these definitions, visual identifiers, fabric-seam pairings, and few-shot
examples to guide every seam decision you make. Do not guess — look up the correct seam
type from this reference and justify your choices using it.

{seam_kb}

────────────────────────────────────────────
STRICT RULES
────────────────────────────────────────────

• You MUST NOT invent closures, buttons, zippers, linings, or stitches.
• You MUST NOT assume stretch unless fabric decision says so.
• You MUST NOT use machine stitch codes (301, 504, etc).
• You MUST NOT hallucinate components not listed in structure.
• If something is not provided → mark as "not applicable".

Your job is to **translate garment design into manufacturable construction logic**, not to design new garments.
"""

    print(f"[DEBUG] construction_decision_agent: running - classification='{classification.get('category') if isinstance(classification, dict) else 'N/A'}'")
    _obj, _think = llm_structured(prompt,ConstructionDecisionModel, enable_thinking=True)
    construction = _obj.model_dump()
    print(f"[DEBUG] construction_decision_agent: returned overall_complexity={construction.get('overall_complexity')}")
    return construction


# =========================================================
# AGENT 5 — MEASUREMENT DECISION (WHAT TO MEASURE)
# =========================================================

def measurement_decision_agent(classification, sizing):
    prompt = f"""
    ROLE: Measurement Planning Agent

    INPUTS:
    Classification:
    {classification}

    Sizing:
    {sizing}

    TASK:
    Define WHAT must be measured and tolerance logic using the DECISION TREE:

    4. Measurement Logic Tree
    Select sample size → S (Default for this logic, but respect input sizing)

    For each measurement point:
     ├── Is it circumference?
     │    └── Tolerance ±1–1.5 cm
     ├── Is it length?
     │    └── Tolerance ±0.5–1 cm
     ├── Is it fitted area?
     │    └── Smaller tolerance

    Designers do not invent measurements. They use:
    - Industry size charts
    - Brand fit block
    - Previous styles

    Why tolerances exist:
    - Fabric stretch
    - Sewing variance
    - Washing shrinkage

    OUTPUT:
    - MeasurementDecisionModel (points, tolerances, sources)
    """
    _obj, _think = llm_structured(prompt, MeasurementDecisionModel, enable_thinking=True)
    return _obj.model_dump()

def measurement_decision_agent(classification, sizing,context):
    prompt = f"""
ROLE: Measurement Planning Agent  
You are a **Senior Apparel Pattern Engineer & Fit Specialist**.  
Your job is to define **what gets measured, how it is measured, and how much variation is allowed** — without inventing any garment features.

You NEVER guess measurements.  
You ONLY define:
• Which measurement points exist
• What category they belong to
• How much tolerance they should have
• Where the values should come from

All numeric values will be filled later from:
• Brand size charts
• Fit blocks
• Graded patterns

────────────────────────────────────────────
INPUTS
────────────────────────────────────────────

GARMENT CLASSIFICATION  
{classification}

SIZING & FIT DATA  
{sizing}

Context already given:
{context}

────────────────────────────────────────────
YOUR RESPONSIBILITY
────────────────────────────────────────────

You must determine:

1. **Which measurement points are required**
2. **What type of measurement each is**
3. **What tolerance class applies**
4. **What reference system should be used**

You are NOT setting actual numbers — only **measurement logic**.

────────────────────────────────────────────
SIZE SELECTION RULE
────────────────────────────────────────────

• Use the sample size specified in `sizing`  
• If not specified, default to **Sample Size = S**  
• All measurement logic is based on this sample size

────────────────────────────────────────────
MEASUREMENT DECISION FRAMEWORK
────────────────────────────────────────────

Each measurement must be classified into ONE of the following:

────────────────────────────
A. CIRCUMFERENCE MEASUREMENTS
────────────────────────────
Used when the body is wrapped by the garment.

Examples:
• Bust
• Waist
• Hip
• Thigh
• Sleeve opening
• Cuff
• Hem sweep

Tolerance:
• ±1.0 to ±1.5 cm  
Because:
• Body movement
• Fabric stretch
• Sewing variance
• Shrinkage

────────────────────────────
B. LENGTH MEASUREMENTS
────────────────────────────
Used for vertical or linear dimensions.

Examples:
• Body length
• Sleeve length
• Shoulder to hem
• Inseam
• Outseam
• Rise

Tolerance:
• ±0.5 to ±1.0 cm  
Because:
• Cutting precision
• Stitch take-up
• Hem turn-ups

────────────────────────────
C. FIT-CRITICAL MEASUREMENTS
────────────────────────────
Used where fit affects comfort, silhouette, or closure.

Examples:
• Armhole
• Neck opening
• Across shoulder
• Front rise
• Back rise
• Waistband

Tolerance:
• Smaller than normal  
Because:
• Minor variation changes fit perception
• Affects wearability

────────────────────────────
D. STRUCTURE-DRIVEN MEASUREMENTS
────────────────────────────
Only included if structure includes the component.

Examples:
• Pocket opening
• Placket width
• Collar height
• Lapel width
• Cuff height

If structure does not include these → DO NOT include them.

────────────────────────────────────────────
WHERE MEASUREMENTS COME FROM
────────────────────────────────────────────

Each measurement must have a **source**, one of:

• Brand Size Chart  
• Brand Fit Block  
• Previous Approved Style  
• Pattern Block  

You do NOT create new measurements.  
You only reference these systems.

────────────────────────────────────────────
WHAT YOU MUST OUTPUT
────────────────────────────────────────────

You must return a **MeasurementDecisionModel** with:

1. `sample_size`
   - The base size used (from sizing or default S)

2. `measurement_points`
   For each point:
   - name (e.g. bust, waist, sleeve_length)
   - category (circumference / length / fit-critical / structure-based)
   - tolerance_class (standard / tight)
   - tolerance_range (e.g. ±1.0–1.5 cm, ±0.5–1.0 cm)
   - reference_source (brand chart, fit block, etc)

3. `measurement_logic_notes`
   High-level reasoning such as:
   - “Stretch fabric allows slightly larger tolerance”
   - “Fitted silhouette requires tighter armhole tolerance”

────────────────────────────────────────────
STRICT RULES
────────────────────────────────────────────

• DO NOT invent measurements not implied by classification or structure.
• DO NOT assume garment components.
• DO NOT generate numeric measurement values.
• DO NOT change sizing logic.
• DO NOT hallucinate size charts.

Your job is to define **how fit is controlled**, not to create measurements.
"""
    print(f"[DEBUG] measurement_decision_agent: sizing sample_size={sizing.get('sample_size') if isinstance(sizing, dict) else sizing}")
    _obj, _think = llm_structured(prompt, MeasurementDecisionModel, enable_thinking=True)
    measurement = _obj.model_dump()
    print(f"[DEBUG] measurement_decision_agent: measurement_points count={len(measurement.get('measurement_points', []))}")
    return measurement


# =========================================================
# AGENT 6 — RESOLVER (FACTORY TRANSLATION)
# =========================================================

def resolver_agent(fabric_decision, construction_decisions, measurement_decisions, structure, images):
    prompt = f"""
ROLE: Factory Translation Agent / Senior Technical Designer

You are converting approved design decisions into FACTORY-READY tech pack data.
You must be precise, conservative, and traceable to inputs.

────────────────────────────────────────────
INPUTS
────────────────────────────────────────────

FABRIC DECISIONS:
{fabric_decision}

CONSTRUCTION DECISIONS:
{construction_decisions}

MEASUREMENT DECISIONS:
{measurement_decisions}

GARMENT STRUCTURE:
{structure}

────────────────────────────────────────────
SECTION 1 — FABRICS
────────────────────────────────────────────

Output format for each fabric:
- description: "Shell Fabric, 90% Cotton / 10% Spandex, 220–260 GSM, 2-way stretch, Matte surface"
- color: Use the garment color from inputs (e.g. "Black")
- position: Where on garment (e.g. "Outer body and one sleeve")

CRITICAL: Use EXACTLY the fabric specified in the context/brand input.
If context says "Silk" → use Silk. Do NOT mix or blend multiple fabric options.
Select ONE primary fabric that matches the context, do NOT create a blend of all mentioned fabrics.

────────────────────────────────────────────
SECTION 2 — SEAMS
────────────────────────────────────────────

For each seam, provide:
- type: Superimposed Seam, Edge Finish, Lapped Seam, etc
- symbol: N/A
- allowance: e.g. "1 cm", "3 cm", etc.
- description: Shoulder Seam, Side Seam, Hem stitching, Center back zipper insertion, etc
- stitch_type: Lockstitch, Overlock, Coverstitch, Blind stitch, etc
- stitch_symbol: N/A
- stitch_size: 2-4mm typically
- machine_type: Single needle machine, 4-thread Overlock, Coverstitch Machine, Invisible Zipper Foot, etc

CRITICAL: Do NOT use technical ISO/ASTM codes (no SSa-1, no 301). Follow the exact terminology and unit formatting in these examples perfectly:

REFERENCE EXAMPLE 1 (Blazer):
1. type: Plain seam | symbol: N/A | allowance: 1 cm | description: Shoulder seam | stitch_type: Lockstitch | stitch_symbol: N/A | stitch_size: 2.5 mm | machine: Single-needle lockstitch
2. type: Plain seam + overlock | symbol: N/A | allowance: 1 cm | description: Side seam | stitch_type: Lockstitch + 3-thread overlock | stitch_symbol: N/A | stitch_size: 2.5 mm | machine: Single-needle & overlock
3. type: Blind hem | symbol: N/A | allowance: 3 cm | description: Hem (jacket bottom & sleeves) | stitch_type: Blind stitch | stitch_symbol: N/A | stitch_size: — | machine: Blind-stitch machine

REFERENCE EXAMPLE 2 (Skirt):
1. type: Lapped/concealed seam | symbol: N/A | allowance: 1 cm | description: Zipper insertion | stitch_type: Lockstitch | stitch_symbol: N/A | stitch_size: 2.5 mm | machine: Zipper foot machine

────────────────────────────────────────────
SECTION 3 — MEASUREMENTS
────────────────────────────────────────────

You MUST generate a FULL GRADED SIZE SCALE. Output one separate Measurement object for EACH size: S, M, L, XL.
Do NOT output only one size. All 4 sizes are REQUIRED.

All measurements are FULL CIRCUMFERENCE (NOT half-body) in INCHES.

CRITICAL GRADED REFERENCE — US Women's Jacket/Outerwear (all values in inches):

| Size  | Bust      | Waist     | Hip       | Shoulder Width | Sleeve Length | Jacket Length |
|-------|-----------|-----------|-----------|----------------|---------------|---------------|
| S     | 35 - 36   | 27 - 28   | 37 - 38   | 14 - 14.5      | 24 - 24.5     | 21 - 22       |
| M     | 37 - 38   | 29 - 30   | 39 - 40   | 14.5 - 15      | 24.5 - 25     | 22 - 23       |
| L     | 39.5 - 41 | 31.5 - 33 | 41.5 - 43 | 15 - 15.5      | 25 - 25.5     | 23 - 24       |
| XL    | 43.5 - 45 | 35.5 - 37 | 45 - 47   | 15.5 - 16      | 25.5 - 26     | 24 - 25       |

Use these exact values as your base. Only adjust slightly if the garment image clearly shows an oversized, cropped, or structured fit.

TOLERANCE FORMAT — Use ± range format (already built into the range values above). Do NOT add separate tolerance values.

Include garment-specific POMs:
- Jackets: include Across Shoulder, Pocket Opening Width
- All: Bust, Waist, Hip, Sleeve Length, Jacket Length

Each measurement MUST have a UNIQUE justification — do NOT use the same justification for all sizes.

────────────────────────────────────────────
SECTION 3B — GARMENT MEASUREMENTS (POM SHEET)
────────────────────────────────────────────

Generate the `pom_measurements` list to be used for the technical sketch callouts.
This is a detailed Point of Measure (POM) sheet for the Base Size (Sample Size).

1. Identify 6-12 critical Points of Measurement (POM) for this garment.
2. Assign a UNIQUE uppercase letter code to each (A, B, C, D, E, etc.).
3. Provide a clear, short description of how to measure it (e.g. "1 inch below armhole").
4. Provide the exact target measurement in cm (e.g. "84").
5. Provide a standard manufacturing tolerance in cm (e.g. "±1.27" or "±0.64").

Ensure you include typical POMs like Chest, Waist, Hip, Shoulder to Shoulder, Sleeve Length, Front Length, Back Length, Armhole depth, etc., depending on the garment.

────────────────────────────────────────────
SECTION 4 — ACCESSORIES
────────────────────────────────────────────

MANDATORY items for EVERY garment:
1. Thread — "100% polyester (recycled polyester) core spun sewing thread" | color: "Matches fabric" | placement: varies
2. Brand Label — 1 pc | placement: "Neck" (inside back neck seam)
3. Size Label — 1 pc | placement: "Below main label"
4. Care Label — 1 pc | placement: "Inside left side seam"
5. Hanger Loop — "Cotton twill tape" | 1 pc | placement: "Inside center back neck seam"

CONDITIONAL items (only if visible in image or structure):
- Concealed/Invisible Zipper (22-24 cm) — ONLY if closure visible/needed for dresses or skirts. Do NOT add to shirts, suits, or coats with buttons or belts.
- Buttons — specify exact count matching what is VISIBLE in image:
  * For shirts/blouses: count front placket buttons (including collar stand button).
  * For cuffs: count buttons on barrel cuff AND gauntlet sleeve plackets (e.g. 2 on cuff + 1 on gauntlet = 3 per sleeve, 6 total for cuffs).
  * Group buttons clearly: e.g. "BUTTONS, 4 HOLE, 12L FOR FRONT, 10L FOR CUFFS, 6 FOR FRONT, 6 FOR CUFFS (3 EACH)"
- Interlining/Fusible — if structured collar/placket/cuffs exist
- Decorative trim — only if visible

CRITICAL FORMATTING RULE FOR ACCESSORY DESCRIPTIONS:
Descriptions MUST be extremely short, concise, and typically just one line. Do NOT write long paragraphs or excessive details. 
Example 1: "BUTTONS, 4 HOLE, PLASTIC BUTTONS, 12 L FOR FRONT, 10 L FOR CUFFS, 6 FOR FRONT, 6 FOR CUFFS (3 EACH)"
Example 2: "BUTTONS, ENGRAVED LOGO DESIGN, GOLD TONE, 4 TOTAL ON POCKETS, 14mm"
Example 3: "THREAD, CORE SPUN POLYESTER"
Example 4: "INTERFACING, FUSED AT COLLAR, PLACKET, CUFFS"

Count accessories by CAREFULLY examining the images. Accurately count all front closure buttons and cuff/gauntlet buttons.

────────────────────────────────────────────
SECTION 5 — CARE LABEL
────────────────────────────────────────────

Must match the EXACT fabric composition from Section 1.
Care instructions must be appropriate for the primary fabric:
- Cotton/Spandex blend: Machine Wash Cold (30°C), Do Not Bleach, Hang Dry, Iron Low Heat
- Silk: Dry Clean Only, Do Not Bleach, Do Not Tumble Dry, Cool Iron
- Wool blend: Professional Dry Clean Only, Do Not Bleach, Line Dry in Shade, Cool Iron
- Polyester: Machine Wash Warm, Do Not Bleach, Tumble Dry Low

Standards: ISO 3758
Must include: "Made in India"

NEW REQUIREMENTS FOR CARE LABEL:
- `care_symbols`: Provide EXACTLY 5 strings representing the ISO care symbols applicable to this garment, chosen from this exact list: ['wash', 'bleach', 'dry', 'iron', 'dry_clean']. (e.g. if you shouldn't bleach, just provide 'bleach', the UI handles the 'do not' symbol variant based on the text. For simplicity, ALWAYS provide these 5 exact strings: ["wash", "bleach", "dry", "iron", "dry_clean"]).
- `translations`: Provide short translated care instructions for the wash label in French ('fr'), German ('de'), Portuguese ('pt'), and Italian ('it'). Format as multi-line strings with HTML `<br>` tags separating composition, wash, and bleach instructions. Example for 'fr': "100% Coton<br>Lavage en machine à froid<br>Ne pas utiliser d'eau de javel"

────────────────────────────────────────────
RULES
────────────────────────────────────────────

- Safest default if multiple options
- If confidence < 0.7 → requires_confirmation = true
- Every output MUST include justification
- Do NOT copy-paste the same justification for different items
- Fabric composition in care label MUST match fabric section exactly

OUTPUT:
- FactoryInstructionModel (fabrics, seams, measurements, accessories, care_label)
"""
    
    print(f"[DEBUG] resolver_agent: starting resolver with fabric_decision keys={list(fabric_decision.keys()) if isinstance(fabric_decision, dict) else 'N/A'}")
    # We analyze images again here just in case specific visual details are needed for trims/finishes
    _analysis, _analysis_think = analyze_images(images, prompt, enable_thinking=True)
    _obj, _think = llm_structured(_analysis, FactoryInstructionModel, enable_thinking=True)
    factory = _obj.model_dump()
    print(f"[DEBUG] resolver_agent: factory_output keys={list(factory.keys())}")
    return factory

# def resolver_agent(fabric_decision, construction_decisions, measurement_decisions, structure, images):
#     prompt = f"""
# ROLE: Factory Translation Agent / Senior Technical Designer  
# You are responsible for converting **approved design, fabric, construction, and measurement decisions** into **factory-executable instructions**.

# You are NOT allowed to invent garment parts, trims, or features.  
# You ONLY finalize and formalize what already exists.

# If something is missing, ambiguous, or not visible → you must mark:
# `requires_confirmation = true`

# ────────────────────────────────────────────
# INPUTS
# ────────────────────────────────────────────

# FABRIC DECISIONS  
# {fabric_decision}

# CONSTRUCTION DECISIONS  
# {construction_decisions}

# MEASUREMENT DECISIONS  
# {measurement_decisions}

# GARMENT STRUCTURE  
# {structure}

# REFERENCE IMAGES  
# (Used ONLY to confirm visibility of trims, closures, stitching, labels, etc)

# ────────────────────────────────────────────
# YOUR JOB
# ────────────────────────────────────────────

# You must translate all decisions into **factory-ready technical pack data**:

# 1. Final fabric specifications
# 2. Exact seam types and stitch systems
# 3. Sample size measurement values
# 4. Trims and accessories list
# 5. Care label & compliance info

# You must stay **100% traceable** to inputs or visible evidence.

# ────────────────────────────────────────────
# SECTION 1 — FABRICS
# ────────────────────────────────────────────

# For each fabric already approved:

# You must output:
# • description  
# • fiber composition %  
# • GSM range  
# • stretch type  
# • surface (matte, twill, rib, etc)  
# • color  
# • where it is used  

# Format style example:
# "Shell Fabric, 90% Cotton / 10% Spandex, 220–260 GSM, 2-way stretch, matte surface, Black, used for outer body"

# DO NOT:
# • Add new fabrics
# • Guess weights without marking uncertainty

# ────────────────────────────────────────────
# SECTION 2 — SEAMS & STITCHING
# ────────────────────────────────────────────

# Using Construction Decisions, you must assign:

# For each seam:
# • seam type (plain, superimposed, lapped, overlocked, coverstitched)
# • seam symbol (SSa-1, SSb-2, LSc-1, etc)
# • seam description (Side seam, Shoulder seam, Center back seam, Hem, Armhole, Zipper seam)
# • stitch type (Lockstitch, Overlock, Coverstitch, Chainstitch)
# • stitch code (301, 401, 504, 603, etc)
# • machine type (Single needle, 4-thread overlock, Flatlock, etc)

# You must choose **safe industry defaults** unless construction logic demands otherwise.

# ────────────────────────────────────────────
# SECTION 3 — MEASUREMENTS
# ────────────────────────────────────────────

# Using Measurement Decisions:
# • Convert sample size S into actual numeric values
# • Base values on standard size S for this garment category
# • Adjust only if image clearly shows oversized, fitted, cropped, etc

# Each measurement must include:
# • POM code (A, B, C, etc)
# • Name (Bust, Waist, Length, Sleeve, etc)
# • Value MUST BE A RANGE (e.g., 30" - 31") incorporating the tolerance. Do NOT provide a single number. All measurement attributes must be given as a range.
# • Tolerance
# • Justification

# If confidence < 70% → requires_confirmation = true

# ────────────────────────────────────────────
# SECTION 4 — ACCESSORIES & TRIMS
# ────────────────────────────────────────────

# List ONLY items that:
# • Exist in structure
# • Are visible in images
# • Or are legally mandatory

# This includes:
# • Zippers (if present)
# • Buttons (if present)
# • Interlining (only if needed for structure)
# • Main label
# • Care label
# • Wash label
# • Sewing thread

# Each item must have:
# • Name
# • Specification
# • Placement
# • Reason for inclusion

# DO NOT add trims “because garments usually have them”.

# ────────────────────────────────────────────
# SECTION 5 — CARE LABEL
# ────────────────────────────────────────────

# Based on fabric decision:
# • Fiber composition %
# • Washing
# • Bleaching
# • Drying
# • Ironing
# • Dry clean
# • Must follow ISO 3758
# • Must include “Made in India”

# ────────────────────────────────────────────
# GLOBAL RULES
# ────────────────────────────────────────────

# • No hallucination
# • No guessing without flagging
# • Every value must have a justification
# • If unsure → requires_confirmation = true
# • Factory must be able to build from this without asking new questions

# ────────────────────────────────────────────
# OUTPUT
# ────────────────────────────────────────────

# Return a **FactoryInstructionModel** with:
# • fabrics
# • seams
# • measurements
# • accessories
# • care_label
# • requires_confirmation flags
# • justifications for every section
# """
    
#     # Re-analyze images to confirm trims, closures, stitching, and placement
#     return llm_structured(
#         analyze_images(images, prompt),
#         FactoryInstructionModel
#     ).model_dump()


# =========================================================
# AGENT 7 — VERIFIER (VETO POWER)
# =========================================================

def verifier_agent(factory_output, full_context):
    prompt = f"""
    ROLE: Independent Technical Auditor

    CONTEXT:
    {json.dumps(full_context, indent=2)}

    OUTPUT TO VERIFY:
    {json.dumps(factory_output, indent=2)}

    TASK:
    Mental Checklist:
    - Can a factory cut this?
    - Can a factory sew this?
    - Can QC measure this?
    - Can merch reorder this?
    - Can legal approve this?

    If any answer is "no" -> flagged as issue.

    OUTPUT:
    - VerificationResult (valid, issues, confidence, fix_suggestions)
    """
    print(f"[DEBUG] verifier_agent: verifying factory_output keys={list(factory_output.keys()) if isinstance(factory_output, dict) else 'N/A'}")
    _obj, _think = llm_structured(prompt, VerificationResult, enable_thinking=True)
    verification = _obj.model_dump()
    print(f"[DEBUG] verifier_agent: verification result -> valid={verification.get('valid')} confidence={verification.get('confidence')}")
    return verification



# =========================================================
# TASK B — ACCESSORIES VERIFICATION AGENT
# =========================================================

def verify_accessories(accessories_list: list, images: list, _report_fn=None, job_progress_base: int = 79) -> list:
    if not accessories_list:
        return accessories_list

    import json as _json

    accessories_summary = "\n".join([
        f"{i+1}. {a.get('description','N/A')} | Qty: {a.get('qty','N/A')} | Color: {a.get('color','N/A')} | Position: {a.get('position','N/A')}"
        for i, a in enumerate(accessories_list)
    ])

    prompt = f"""You are a senior technical designer reviewing a garment accessories list for accuracy.
ACCESSORIES LIST FROM AI (may contain errors):\n{accessories_summary}

YOUR TASK:
1. Look carefully at the garment in the images.
2. BUTTON ACCURACY & COUNTING:
   - Count buttons precisely: count center front placket buttons (including collar stand button).
   - Check sleeve cuffs: count both cuff closure buttons and gauntlet placket buttons on each sleeve (e.g. 2 cuff + 1 gauntlet = 3 buttons each cuff, 6 total for cuffs).
   - If buttons are present, specify the exact count for front and for cuffs.
3. REMOVE accessories ONLY if they are clearly NOT visible and NOT structurally necessary (e.g., hallucinated zippers on a shirt, or extra belts).
   - CRITICAL: Do NOT remove buttons if there is a placket, cuff, or closure that requires them, even if small.
4. ADD any obvious accessories that ARE clearly visible but were missed (like interfacing at collar/cuffs, spare button).
5. KEEP all accessories that are genuinely present or mandatory (like labels, fusible interfacing, and thread).

Return ONLY valid JSON — a list of objects with these exact fields:
[
  {{"description": "...", "quantity_per_style": "...", "color": "...", "position": "...", "justification": "..."}}
]"""

    try:
        raw, _think = analyze_images(images, prompt, enable_thinking=True)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        verified = _json.loads(raw)
        if isinstance(verified, list):
            msg = f"{len(verified)} accessories verified"
            detail = _think or f"Vision check: removed hallucinations, confirmed visible items."
            if _report_fn:
                _report_fn("Accessories Verification", msg, detail, job_progress_base)
            return verified
    except Exception as e:
        print(f"[verify_accessories] Error: {e}")

    return accessories_list

# =========================================================
# MAIN PIPELINE
# =========================================================

def generate_techpack(images, context, generate=False, sample_size="M", progress_callback=None, brand_logo_path=None):
    def _report(step, decision, reasoning, progress):
        print(f"[AGENT] {step} → {decision}")
        if progress_callback:
            try:
                progress_callback(step, decision, reasoning, progress)
            except Exception as e:
                print(f"[progress_callback error] {e}")

    # 1. Load master
    with open("data/master.json") as f:
        master = deepcopy(json.load(f))
    print(f"[DEBUG] generate_techpack: loaded master.json, top-level keys={list(master.keys())}")
    for i in range(1, 11):
        ensure_page(master, f"page_{i}")

    # 2. Header
    header_prompt = f"""
    Generate FACTORY tech pack header.
    
    Logic for style name generation : [Collection Initial]-[Brand Initial]-[Season Code][2-Digit Year]-[Garment Type]
    
    CRITICAL RULES FOR STYLE NAME:
    1. [Collection Initial]: First letter of each word in the Collection name in order.
       Example: "JC Private Collection" → J (from JC) + P (from Private) + C (from Collection) = JPC.
    2. [Brand Initial]: First letter of the Brand name.
       Example: Brand "Discrete" → D.
    3. [Season Code][2-Digit Year]:
       - Fall/Winter → FA/WI
       - Spring/Summer → SP/SU
       Always format with slash between seasons and append the 2-digit year (e.g. FA/WI25).
    4. [Garment Type]: 3-letter uppercase abbreviation for the garment type.
       Use these standard fashion nomenclature codes:
       - Cocktail Dress → CDR
       - Dress (General/Casual) → DRS
       - Evening Gown → GWN
       - Turtleneck → TRT
       - Light Jacket → LJK
       - Jacket → JKT
       - Coat → COA
       - Suit → SUT
       - Blazer → BLZ
       - Shirt → SHT
       - Blouse → BLO
       - Pants / Trousers → PNT
       - Skirt → SKT
       - Shorts → SRT
       - Jumpsuit → JMP
       - Sweater / Knitwear → SWT
       - Cardigan → CRD
       - Vest → VST
       - Top → TOP
    
    Examples:
    - Collection "JC Private Collection", Brand "Discrete", Season "Fall/Winter 25", Garment "Cocktail Dress" → JPC-D-FA/WI25-CDR
    - Collection "JC Private Collection", Brand "Discrete", Season "Fall/Winter 25", Garment "Turtleneck" → JPC-D-FA/WI25-TRT
    - Collection "JC Private Collection", Brand "Discrete", Season "Fall/Winter 25", Garment "Light Jacket" → JPC-D-FA/WI25-LJK
    
    Inputs:
    {context}
    
    Category Rule:
    category MUST be strictly one of these three values:
    - "women wear"
    - "kids' wear"
    - "men's wear"
    Never use "outerwear", "innerwear", "apparel", "dress", etc. Always assign one of the 3 demographic wear categories above.
    
    Sample Size: {sample_size} (You MUST set sample_size_1st exactly to this value)
    Date: If a date is provided in the inputs (e.g. 08-11-2025), use that exact date. Otherwise use {datetime.datetime.now().strftime("%d/%m/%Y")}.

    description should be one liner, such as "women's light jacket".
    """

    print("trying for header")
    _obj, _think = llm_structured(header_prompt, TechPackHeader, enable_thinking=True)
    header = _obj.model_dump()
    print(f"[DEBUG] generate_techpack: header generated -> style_name={header.get('style_name') if isinstance(header, dict) else 'N/A'}")
    master["header"] = header

    print("got header ,header")

    # 3. Page 1 — Detect front/back from filenames
    front_img = images[0]
    back_img = images[1] if len(images) > 1 else images[0]

    # Auto-detect front/back from filename
    for img in images:
        img_lower = img.lower()
        if "front" in img_lower:
            front_img = img
        elif "back" in img_lower:
            back_img = img

    master["page_1"].update({
        "garment_front_view_url": front_img,
        "garment_back_view_url": back_img,
        "style_number": header["style_name"],
        "date": header["date"],
        "brand_name": header["brand"],
        "collection_name": header["collection"],
        "season": header["season"],
    })

    print(f"[DEBUG] generate_techpack: page_1 populated -> brand={master['page_1']['brand_name']} collection={master['page_1']['collection_name']}")

    # Brand logo: use user-uploaded logo if provided, otherwise AI-generate one
    if brand_logo_path and os.path.exists(brand_logo_path):
        print(f"[DEBUG] generate_techpack: using uploaded brand logo from {brand_logo_path}")
        master["page_1"]["brand_logo"] = brand_logo_path
    else:
        first_page_logo_prompt = f"""replace swanky by collection name {master['page_1']['brand_name']},also replace collection name to {master['page_1']['collection_name']}"""
        if generate == True:
            generate_image(first_page_logo_prompt, "assets/first_page_logo.png", "assets/first_page_logo_current.png")
        master["page_1"]["brand_logo"] = "assets/first_page_logo_current.png"
        print(f"[DEBUG] generate_techpack: using AI-generated brand logo")

    # 4. Color
    colors_result = extract_garment_color(images)
    colors = colors_result['colors']
    
    # Import scraper here to avoid circular imports or slow startup
    from pantone_scraper import get_tcx_options
    
    for c in colors:
        # Only run the scraper here if the new MULTI_PANTONE pipeline didn't already populate options
        if not c.get('pantone_options'):
            print(f"[DEBUG] generate_techpack: Scrape Pantone options for {c['color_hex']} ({c['color_name']})")
            scraped_options = get_tcx_options(c['color_hex'])
            
            if scraped_options:
                # Enrich scraped options with the parent hex so the UI color block doesn't break
                for opt in scraped_options:
                    code = opt.get("code", "")
                    if " TCX" not in code: code += " TCX"
                    opt["hex"] = c['color_hex']

                c['pantone_options'] = scraped_options
                # Override LLM guess with actual top match from Pantone API
                c['pantone_tcx'] = scraped_options[0]['code']
                print(f"[DEBUG] generate_techpack: Selected TCX {c['pantone_tcx']} from scraped options")
            else:
                print(f"[DEBUG] generate_techpack: No options found, falling back to LLM guess: {c['pantone_tcx']}")

    master['page_2']['optional_colors'] = colors
    color = colors[0]
    master["page_2"].update(color)
    print(f"[DEBUG] generate_techpack: extracted color -> name={color.get('color_name')} hex={color.get('color_hex')} options_count={len(color.get('pantone_options', []))}")

    # 5. AGENTS EXECUTION
    print("--- Executing Vision Agent ---")
    vision = vision_agent(images)
    print(f"[DEBUG] generate_techpack: vision raw text preview: {vision['raw_observation_text'][:160].replace('\n',' ')}")
    
    print("--- Executing Classification Agent ---")
    classification = garment_identifier_agent(vision["structure"])
    print(f"[DEBUG] generate_techpack: classification -> {classification}")
    
    print("--- Executing Fabric Decision Agent ---")
    fabric_decision = fabric_decision_agent(classification, vision["structure"], context,color)
    print("fabiorc decisionj ", fabric_decision)
    print(f"[DEBUG] generate_techpack: fabric_decision -> {fabric_decision}")
    
    print("--- Executing Construction Decision Agent ---")
    construction_decisions = construction_decision_agent(classification, fabric_decision, vision["structure"])
    print(f"[DEBUG] generate_techpack: construction_decisions overall_complexity={construction_decisions.get('overall_complexity')}")
    
    print("--- Executing Measurement Decision Agent ---")
    measurement_decisions = measurement_decision_agent(classification, {
        "market": "US Women",
        "sample_size": sample_size,
        "size_range": ["S", "M", "L", "XL"] # Default range
    },context)
    print(f"[DEBUG] generate_techpack: measurement_decisions sample_size={measurement_decisions.get('sample_size')}")

    # 6. Resolver
    print("--- Executing Resolver Agent ---")
    factory_output = resolver_agent(
        fabric_decision,
        construction_decisions,
        measurement_decisions,
        vision["structure"],
        images
    )
    print(f"[DEBUG] generate_techpack: factory_output keys={list(factory_output.keys())}")

    # 7. Verification
    print("--- Executing Verifier Agent ---")
    verification = verifier_agent(factory_output, {
        "vision": vision,
        "classification": classification,
        "fabric": fabric_decision,
        "construction": construction_decisions,
        "measurements": measurement_decisions
    })

    if not verification["valid"]:
        print("⚠️ VERIFICATION FAILED:", verification)
    else:
        print("✅ Verification Passed")

    # 8. Fill pages
    # Page 2 Details (keep legacy prompt or use vision text - using legacy prompt for specific formatting)
    page2_prompt = f"""
You are a tech pack designer writing garment details for a manufacturer.

Write in PLAIN TEXT only. No markdown, no bold, no headers, no bullet points with dashes.
Keep it SHORT — max 6-8 lines total.

Use EXACTLY this format:

Silhouette: [one line description]
Sleeves: [one line description]
Other Features:
[feature 1]
[feature 2]
[feature 3]

Context from vision: {vision["raw_observation_text"]}

EXAMPLE OUTPUT (follow this style exactly):
Silhouette: Body-hugging fit at the top, flowing into an A-line skirt with asymmetrical hem
Sleeves: Full-length fitted sleeves with clean hems
Other Features:
High turtleneck collar, close-fitting
Thigh-high front slit on the left side
Side-gathered ruched detail at the left waist

RULES:
- NO markdown formatting (no #, **, -, *)
- NO headers or titles
- Plain text ONLY
- Keep it concise — 6-8 lines maximum

For Outerwear/Coats/Trench Coats/Jackets:
- Identify lapel type (Notched, Peak, Shawl)
- Identify closure mechanism (Double-breasted, Single-breasted, Wrap front with tie belt)
- Identify sleeve construction (Set-in, Raglan, Raglan-style ease)
- Do NOT use generic dress terms for coats. Use outerwear terminology.
"""
    page2_details, _p2_think = analyze_images(images, page2_prompt, enable_thinking=True)
    _report("Detail Analysis", "Analyzed details", _p2_think, 10)
    
    master["page_2"].update({
        "details": page2_details,
        "front_image_url": front_img,
        "back_image_url": back_img,
    })
    
    combined_image = combine_images_horizontally(images, "assets/combined.png")

    original_input_images = images
    extra_input_images = original_input_images[2:]

    n_crops_cfg = int(os.getenv("DETAIL_CROP_COUNT", "6"))
    ai_crops = ai_crop_detail_regions(
        images=original_input_images,
        garment_details=page2_details,
        output_dir="assets",
        n_crops=n_crops_cfg,
    )
    _report("Detail Cropping",
            f"AI crops: {len(ai_crops)} regions identified and cropped",
            f"Vision model cropped {len(ai_crops)} detail zones." if ai_crops else "Found no regions — falling back to grid crops",
            83)

    garment_cat = classification.get("category", "").lower()
    if garment_cat in ("outerwear",) or "jacket" in garment_cat or "coat" in garment_cat:
        grid_height = 1400
    else:
        grid_height = 575
    grid_crops = split_into_grids(combined_image, "assets", grid_height=grid_height, extra_width=190)

    def _is_useful_crop(path: str, white_threshold: float = 0.90) -> bool:
        try:
            from PIL import Image as _PILImage
            import numpy as _np
            _img = _PILImage.open(path).convert("RGB")
            _arr = _np.array(_img)
            white_px = _np.sum(_np.all(_arr > 240, axis=2))
            return (white_px / (_arr.shape[0] * _arr.shape[1])) < white_threshold
        except Exception:
            return True

    useful_grid_crops = [p for p in grid_crops if _is_useful_crop(p)]
    detail_pool = ai_crops if ai_crops else (extra_input_images + useful_grid_crops)

    master["page_2"].update({
        "detail_images": detail_pool[:6],
        "detail_image_1_url": detail_pool[0] if len(detail_pool) > 0 else None,
        "detail_image_2_url": detail_pool[1] if len(detail_pool) > 1 else None,
        "detail_image_3_url": detail_pool[2] if len(detail_pool) > 2 else None,
        "detail_image_4_url": detail_pool[3] if len(detail_pool) > 3 else None,
        "detail_image_5_url": detail_pool[4] if len(detail_pool) > 4 else None,
        "detail_image_6_url": detail_pool[5] if len(detail_pool) > 5 else None,
        "optional_image_urls": images  # keep original list
    })


    # page 3

    desc_str = (master.get("header", {}).get("description", "") + " " + classification.get("category", "") + " " + master.get("header", {}).get("style_name", "")).lower()
    is_two_piece = any(kw in desc_str for kw in ("suit", "set", "two-piece", "2-piece", "skirt suit", "pant suit", "co-ord", "tracksuit", "sut"))

    if is_two_piece:
        layout_instruction = """Layout Requirements:
- This garment consists of two separate segments (separate upper wear and separate bottom wear).
- Present the four garment parts horizontally side-by-side:
  [Top Wear Front]  [Bottom Wear Front]  [Top Wear Back]  [Bottom Wear Back]
- Both upper wear and bottom wear must be clearly depicted front and back without model or human body."""
    else:
        layout_instruction = """Layout Requirements (CRITICAL):
- Create the technical sketch showing Front and Back views SIDE-BY-SIDE horizontally on a wide landscape canvas.
- DO NOT draw them stacked vertically top-to-bottom.
- Left side: [Front View]
- Right side: [Back View]"""

    technical_sketch_prompt = f"""Convert the provided image of a model wearing a garment into a professional fashion technical sketch suitable for a production tech pack.

Output Requirements:
- STRICTLY BLACK AND WHITE LINE ART ONLY. ABSOLUTELY NO COLOR in the garment drawing.
- Create clean 2D vector-style black line art on pure white body (#ffffff). DO NOT fill the garment with solid colors like blue, red, etc.
- White background, no color, no background textures (collar/stand may have subtle grayscale shading if visible in reference)
- Garment only (remove model facial and body features)

{layout_instruction}

Strict Feature & Count Accuracy:
- Accurately reflect the exact count of buttons, pockets, seams, and trims seen in the reference photos and accessories specification.
- Vertical Proportions: Maintain tall, elongated vertical fashion proportions. Do NOT draw garments compressed, short-heighted, or stumpy. Dresses and tops must have an elegant, elongated silhouette.
- SLEEVE COMPLETENESS (CRITICAL):
  * Both left and right sleeves MUST be drawn completely with finished cuffs on both Front and Back views.
  * Leave generous canvas margin/padding around both sides so neither sleeve is cropped, truncated, or omitted at canvas edges.
- HEMLINE BALANCE & EQUAL FRONT/BACK LENGTH RULE (CRITICAL CHECK):
  * For T-shirts, nightdresses, shirts, blouses, tops, and dresses: Check the front and back hem levels very carefully.
  * DO NOT artificially lengthen the back panel, extend the backside lower, or add an unwanted hi-low / curved scoop drop hem.
  * Unless the garment reference explicitly displays a hi-low / dipped back hem design, the FRONT and BACK views MUST HAVE EXACTLY EQUAL VERTICAL LENGTH.
  * The bottom hemline of the back view MUST align horizontally at the exact same vertical level as the front view hemline.
- BUTTON COUNT ACCOUNTING & DISAMBIGUATION (COLLAR STAND VS PLACKET):
  * When a shirt/blouse specifies a total count of front buttons (e.g., 6 buttons), this count ALREADY INCLUDES the collar stand button.
  * Exact breakdown: 1 collar stand button + 5 front placket buttons = 6 buttons TOTAL.
  * DO NOT draw 6 placket buttons and then add an extra collar button (which erroneously totals 7).
- Zipper Placement: Check closure location precisely. If the garment has a side invisible zipper, place it at the side seam and leave the center back as a clean vertical seam. Only draw a center back zipper if it genuinely opens at center back.
- Sleeve cuffs: Accurately show buttons on barrel cuffs AND sleeve gauntlet plackets (e.g. 2 cuff + 1 gauntlet = 3 per sleeve).
- Construction accuracy: Draw all seams, darts, and construction details (like center back seams or princess seams) exactly as described in the Seams & Construction document.

Annotation & Labeling (CRITICAL ACCURACY):
- BRAND & SIZE LABEL: In the Front View, inside the inner back neckline/collar opening, always illustrate the small rectangular brand neck tag, labeled with a leader line: 'BRAND & SIZE LABEL'.
- Use clean, straight, thin RED LEADER LINES connecting each uppercase label text EXACTLY to its corresponding garment feature.
- The tip of the leader line MUST touch the exact feature being described. Do not let lines float aimlessly or point to the wrong area.
- DO NOT let leader lines cross or intersect each other. Ensure text is clearly legible without overlapping.
- CONCISE CALLOUT LABELS: Use standard short 1-4 word fashion tech pack callouts (e.g. 'COLLAR', 'FRONT PLACKET', 'LONG SLEEVES WITH CUFF', 'BACK YOKE', 'CENTER BACK SEAM'). Do NOT write long paragraphs.
- CRITICAL: Keep ONLY the garment drawings, leader lines, and callout label text in the image.
  DO NOT include any bottom specification bars, SEAMS & TRIMS note boxes, borders, titles, 'FRONT VIEW'/'BACK VIEW' text, or headers in the image.

Don't draw any lines or zippers or buttons or any other details, until specified in accessories.

Garment Details to Label:
{page2_details}

Seams & Construction:
{construction_decisions}

Accessories / Trims / Hardware:
{factory_output.get("accessories", [])}

Style Guidance:
- Technical flat illustration (fashion CAD)
- Precise proportions and symmetry
- Minimalist, professional, factory-ready

Do not invent details. Only label what is explicitly provided.
"""

    # Support two flows: "normal" text prompt or "json" prompt
    sketch_prompt_flow = os.getenv("SKETCH_PROMPT_FLOW", "normal").strip().lower()
    if sketch_prompt_flow == "json":
        print("[INFO] Using structured JSON prompt flow for technical sketch generation.")
        technical_sketch_prompt = build_json_sketch_prompt(
            page2_details=page2_details,
            construction_decisions=construction_decisions,
            accessories=factory_output.get("accessories", []),
            is_two_piece=is_two_piece,
            garment_type=structure.get("garment_type", ""),
            brand_collection=master.get("page_1", {}).get("collection_name", "")
        )
    elif sketch_prompt_flow == "converted_json":
        print("[INFO] Using converted JSON prompt flow for technical sketch generation.")
        technical_sketch_prompt = convert_text_to_json_prompt(technical_sketch_prompt)
    else:
        print("[INFO] Using standard text prompt flow for technical sketch generation.")

    if generate:
        use_pro = os.getenv("IMAGE_USE_PRO", "false").lower() == "true"
        image_seed = int(os.getenv("IMAGE_SEED", "42")) if os.getenv("IMAGE_SEED", "42").isdigit() else 42
        input_refs = images if images else ["assets/combined.png"]
        generate_image(
            technical_sketch_prompt,
            "assets/combined.png",
            "assets/technical_sketch.png",
            use_pro=use_pro,
            seed=image_seed,
            image_paths=input_refs
        )
        sketch_path, sketch_log = verify_and_regenerate(
            image_path="assets/technical_sketch.png",
            image_type="technical_sketch",
            original_prompt=technical_sketch_prompt,
            generate_fn=lambda p, ref, out, use_pro=use_pro: generate_image(p, ref, out, use_pro=use_pro, seed=image_seed, image_paths=input_refs),
            ref_image="assets/combined.png",
        )
        sketch_path = format_technical_sketch(sketch_path, is_two_piece=is_two_piece, output_path="assets/technical_sketch_formatted.png")
        master["page_3"]["technical_sketch_img"] = sketch_path
        sketch_result = sketch_log[-1]
        _report("Sketch Verification", f"{'✅ Passed' if sketch_result['valid'] else '⚠️ Regenerated'}", sketch_result.get('thinking', ''), 85)
    else:
        sketch_path = format_technical_sketch("assets/technical_sketch.png", is_two_piece=is_two_piece, output_path="assets/technical_sketch_formatted.png")
        master['page_3']['technical_sketch_img'] = sketch_path

    brand_label_prompt = f"""Create a brand label for a garment with:
    - Brand/Collection name: {master['page_1']['collection_name']}
    - Garment description: {master['header']['description']}
    - Website: https://jccobrand.com/

    Replace any existing text on the label with the above details.
    Keep the same clean, minimal label design style.
    """

    if generate:
        generate_image(brand_label_prompt, "assets/brand_label.png", "assets/brand_label_final.png", use_pro=False)
        brand_path, brand_log = verify_and_regenerate(
            image_path="assets/brand_label_final.png",
            image_type="brand_label",
            original_prompt=brand_label_prompt,
            generate_fn=lambda p, ref, out, use_pro=False: generate_image(p, ref, out, use_pro=use_pro),
            ref_image="assets/brand_label.png",
        )
        master["page_3"]["brand_label_img"] = brand_path
        brand_result = brand_log[-1]
        _report("Brand Label Verification", f"{'✅ Passed' if brand_result['valid'] else '⚠️ Regenerated'}", brand_result.get('thinking', ''), 87)
    else:
        print("going in else for brand label")
        master['page_3']['brand_label_img'] = "assets/brand_label_final.png"

    # Care Label image generation removed. Now rendering natively in HTML.
    _report("Care Label Verification", "✅ Using Native HTML", "Switched to HTML-based Care Label layout", 89)



    measurement_diagram = f"""A professional fashion technical flat (tech pack measurement diagram) of given image garment, shown in front view and back view side-by-side on a clean white background.

    Draw everything using thin black vector CAD-style lines with no shading, no textures, and no colors.

    On the front view, include red technical measurement guides:

    horizontal, vertical, and diagonal double-arrow dimension lines

    dots at measurement points

    empty letter placeholders (A, B, C, D, E, F…) placed near each measurement line

    Do NOT add text labels or values — only the letters should appear so that labels can be added later.

    Layout must look like a factory-ready fashion tech pack page used for clothing manufacturing.

    measurement details:
    {factory_output.get('pom_measurements', [])}"""

    if generate:
        generate_image(measurement_diagram, combined_image, "assets/measurement_diagram.png", use_pro=False)
        meas_path, meas_log = verify_and_regenerate(
            image_path="assets/measurement_diagram.png",
            image_type="measurement_diagram",
            original_prompt=measurement_diagram,
            generate_fn=lambda p, ref, out, use_pro=False: generate_image(p, ref, out, use_pro=use_pro),
            ref_image=combined_image,
        )
        master["page_10"]["measurement_image_url"] = meas_path
        meas_result = meas_log[-1]
        _report("Measurement Diagram Verification", f"{'✅ Passed' if meas_result['valid'] else '⚠️ Regenerated'}", meas_result.get('thinking', ''), 91)
    else:
        master['page_10']['measurement_image_url'] = "assets/measurement_diagram.png"

    master["page_4"]["accessories"] = verify_accessories(factory_output.get("accessories", []), images, _report, 79)
    master["page_5"]["seams"] = factory_output.get("seams", [])
    master["page_6"]["measurements"] = factory_output.get("measurements", []) # Graded Size Chart (S, M, L, XL)
    master["page_10"]["measurements"] = factory_output.get("pom_measurements", []) # Detailed POM table
    master["page_7"]["fabrics"] = factory_output.get("fabrics", [])
    
    # # Page 7 Quality Standards (Agent call)
    # _obj, _think = llm_structured(
    #     f"""Generate quality standards for this {classification['category']}. Return JSON only.
    #     example quality standards are Dimensional Stability , Color Fastness to Washing, Color Fastness to Rubbing, Flammability (optional), etc could be possible based on fabric and garment information.
    #     """,
    #     QualityStandardsList
    # # replaced above

    _obj, _think = llm_structured(
    f"""
    ROLE  
    You are a **Factory Quality Assurance Engineer** preparing the official **buyer test requirement sheet** for this garment.

    You must select only **real, industry-standard apparel tests** that truly apply to this product.

    You do NOT invent tests.  
    You do NOT include unnecessary tests.  
    You only include tests that are required based on fabric, color, garment type and construction.

    ────────────────────────────────────────
    INPUT DATA
    ────────────────────────────────────────

    GARMENT CLASSIFICATION  
    {classification}

    FABRIC & MATERIALS  
    {fabric_decision}

    CONSTRUCTION & TRIMS  
    {construction_decisions}

    ────────────────────────────────────────
    WHAT YOU MUST DO
    ────────────────────────────────────────

    From the data above, decide which **real apparel QA tests** are required for this garment.

    All tests must come from **recognized apparel standards** such as:
    ISO, AATCC, ASTM, EN, BS.

    You are selecting from industry practice — not inventing.

    ────────────────────────────────────────
    SELECTION RULES
    ────────────────────────────────────────

    A test is allowed ONLY if it is justified by:

    • Fabric type (woven, knit, stretch, brushed, coated, etc)  
    • Fiber content (cotton, polyester, elastane, wool, viscose, etc)  
    • Color (dark, bright, dyed, printed, pigment, etc)  
    • Garment type (dress, shirt, coat, pants, knitwear, etc)  
    • Construction (lining, stretch seams, zippers, buttons, fusings, etc)  
    • End use (outerwear, daily wear, active, sleepwear, etc)

    If a component does not exist → its test MUST NOT appear.

    ────────────────────────────────────────
    CORE TESTS (normally required)
    ────────────────────────────────────────

    Include unless clearly not applicable:

    • Dimensional Stability (washing shrinkage)  
    • Color Fastness to Washing  
    • Color Fastness to Rubbing (Dry & Wet)  
    • Seam Strength  
    • Appearance After Washing  

    ────────────────────────────────────────
    CONDITIONAL TESTS
    ────────────────────────────────────────

    Include only if the garment data requires it:

    • Color Fastness to Light → outdoor or light-sensitive colors  
    • Pilling Resistance → knits, brushed, fleece, soft surfaces  
    • Stretch & Recovery → elastane, spandex, knit, stretch woven  
    • Bursting Strength → knit or stretch fabrics  
    • Abrasion Resistance → outerwear, heavy-use garments  
    • Zipper Strength → only if zippers exist  
    • Button Pull Strength → only if buttons exist  
    • Seam Slippage → fine, smooth woven fabrics (satin, silk, etc)  
    • Flammability → kidswear, nightwear, or regulated markets  

    ────────────────────────────────────────
    OUTPUT FORMAT (STRICT)
    ────────────────────────────────────────

    Return a **QualityStandardsList** in JSON.

    Each item must have exactly these fields:

    • test_name  
    • method (ISO / AATCC / ASTM etc)  
    • requirement (numeric or graded threshold if applicable)  
    • comments (why this test applies to THIS garment)

    The comments must reference fabric, color, construction, or garment type.

    ────────────────────────────────────────
    FORBIDDEN
    ────────────────────────────────────────

    • No invented tests  
    • No vague standards  
    • No unnecessary testing  
    • No components that do not exist  
    • No marketing language  
    • No assumptions  

    Think like a **factory QA lab preparing a buyer compliance sheet**.

    Return JSON only.

    ────────────────────────────────────────
    REFERENCE STYLE
    ────────────────────────────────────────

    Dimensional Stability  
    Method: ISO 5077  
    Requirement: Max Shrinkage ±2%  
    Comments: Ensures garment retains correct sizing after washing or dry cleaning  

    Color Fastness to Washing  
    Method: ISO 105-C06  
    Requirement: ≥ Grade 4  
    Comments: Prevents dyed fabric from bleeding or fading during laundering  

    Color Fastness to Rubbing  
    Method: ISO 105-X12  
    Requirement: Dry ≥ 4, Wet ≥ 3.5  
    Comments: Critical for dark or saturated colors to avoid staining  

    Seam Slippage  
    Method: ISO 13936-2  
    Requirement: Max 5 mm @ 60 N  
    Comments: Required for smooth woven fabrics that may pull apart at seams  

    Pilling Resistance  
    Method: ISO 12945-2  
    Requirement: ≥ Grade 3–4  
    Comments: Prevents surface fuzzing in knit or brushed fabrics  

    Flammability  
    Method: ISO 15025  
    Requirement: Pass  
    Comments: Required for sleepwear or regulated export markets
    """
    , QualityStandardsList, enable_thinking=True)
    master["page_7"]["quality_standards"] = _obj.model_dump().get("quality_standards", [])


    # Page 8 Size Chart (Agent call based on measurements)
    # master["page_8"]["size_chart"] = llm_structured(
    #     f"Generate size chart for {classification['market']} {classification['category']} Size {classification['size_range'] if 'size_range' in classification else 'S-XL'}. Return JSON only.",
    #     SizeChartList
    # # replaced above

    _obj, _think = llm_structured(
        f"""
    ROLE: Apparel Size & Fit Standards Engineer  

    You are responsible for producing a **commercial size chart** that customers and factories will use.

    You must follow **real-world apparel sizing logic** for the specified market and garment type.

    ────────────────────────────────────────────
    INPUT
    ────────────────────────────────────────────

    MARKET  
    {classification['market']}

    GARMENT CATEGORY  
    {classification['category']}

    SIZE RANGE  
    {classification['size_range'] if 'size_range' in classification else 'S–XL'}

    FABRIC & FIT CONTEXT  
    {fabric_decision}

    MEASUREMENT FRAMEWORK  
    {measurement_decisions}

    ────────────────────────────────────────────
    YOUR RESPONSIBILITY
    ────────────────────────────────────────────

    You must generate a **brand-usable size chart** that:

    • Matches the market (US, EU, India, etc)  
    • Matches the garment category (top, dress, pants, outerwear, etc)  
    • Respects fabric stretch and fit logic  
    • Is compatible with the sample size and tolerances  

    You are not inventing random numbers.  
    You are generating **industry-standard size values**.

    ────────────────────────────────────────────
    MARKET RULES
    ────────────────────────────────────────────

    Use standard grading logic for the given market.

    Examples:
    • India / Asia → slightly slimmer fit than US  
    • US → fuller grading  
    • EU → metric-based, proportional grading  

    ────────────────────────────────────────────
    FABRIC ADJUSTMENT RULES
    ────────────────────────────────────────────

    If fabric has:
    • Stretch → slightly smaller body measurements allowed  
    • No stretch → more ease added  
    • Knit → more tolerance  
    • Woven → tighter control  

    ────────────────────────────────────────────
    MEASUREMENT COVERAGE
    ────────────────────────────────────────────

    Include ONLY measurements that are valid for this garment category:
    Examples:
    • Tops → bust, length, shoulder, sleeve  
    • Bottoms → waist, hip, inseam, rise  
    • Dresses → bust, waist, hip, length  

    DO NOT include irrelevant points.

    ────────────────────────────────────────────
    WHAT YOU MUST OUTPUT
    ────────────────────────────────────────────

    Return a **SizeChartList** with:

    For each size (S, M, L, XL, etc):
    • size  
    • measurement values for all valid POMs  
    • unit (cm)  

    All sizes must be **graded consistently** from the base size.

    ────────────────────────────────────────────
    STRICT RULES
    ────────────────────────────────────────────

    • No random guessing  
    • No fashion-blog charts  
    • No missing POMs  
    • All sizes must be proportional  
    • Numbers must make manufacturing sense  

    Return JSON only.
    """,
        SizeChartList, enable_thinking=True)
    master["page_8"]["size_chart"] = _obj.model_dump().get("size_chart", [])
    if len(original_input_images) > 0:
        master["page_8"]["reference_image_front"] = original_input_images[0]
    if len(original_input_images) > 1:
        master["page_8"]["reference_image_back"] = original_input_images[1]

    
    # Page 9 Care
    master["page_9"]["wash_label"] = factory_output.get("care_label", {})
    ensure_page_9_contract(master["page_9"])
    

    final_json = map_json(master)


    # 9. Save
    with open("data/master_filled.json", "w") as f:
        json.dump(final_json, f, indent=4)
        
    with open("data/master_draft.json", "w") as f:
        json.dump(final_json, f, indent=4)

    return generatePdf()

if __name__ == "__main__":
    context = """
    Brand: JC & Co
    Collection: Grandiose
    Season: Fall/Winter 25
    Garment: Wrap coat dress
    Fabric to be used: Gabardine / Wool blends
    Size Range: S–XL

    Measurements
-    US Women's Size
- 4. Sample Size - Small and Size Range - Small to Extra Large
- Now we expect AI to follow our designer's workflow and use these basic inputs to develop a comprehensive tech pack as per our layout.
- Let me know if you have any questions
- 
- Size Category	US Size	Bust	Natural Waist	Hip
- XXS	0	30.5	23	—
- XS	0	31.5	24	—
- XS	2	32.5	25	—
- S	4	33.5	26	—
- S	6	34.5	27	—
- M	8	35.5	28	—
- M	10	36.5	29	—
- L	12	38	30.5	—
- B. Bottoms – Regular & Short (in inches)
- Size Category	US Size	Waist	Hip
- XXXS	0	23	33
- XXS	0	24	34
- XS	0	25	35
- XS	2	26	36
- S	4	27	37
- S	6	28	38
- M	8	29	39
- M	10	30	40
- L	12	31.5	41.5
- L	14	33	43
- XL	16	35.5	45.5

    """
    
    # Example usage (commented out to avoid auto-run on import if needed, but safe here)
    generate_techpack(["assets/front.png", "assets/back.png"], context, True)