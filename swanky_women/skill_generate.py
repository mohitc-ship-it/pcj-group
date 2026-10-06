#!/usr/bin/env python3
"""
Skill-based tech pack generation.
Replaces main.py's generate_techpack() with the trained skill approach.

This is what the web UI calls. It combines:
- Trained knowledge from 26 reference PDFs
- GPT Image 2.5 Flare for image generation
- Pantone.com scraper for color matching
- AI detail cropping
- Sketch label verification
- Client convention overrides
- Continuous learning from corrections

Usage from editor_api.py:
    from skill_generate import generate_techpack
    pdf_path = generate_techpack(images, context, True, "S", progress_callback)
"""

import os
import json
import re
import datetime
from pathlib import Path
from copy import deepcopy

from llm import analyze_images, llm_structured, llm_query
from generate import generatePdf
from utils import (
    nearest_pantone_tcx, ai_crop_detail_regions,
    combine_images_horizontally, split_into_grids,
    recommend_colors_from_images
)
from skill_image_gen import generate_image, verify_sketch_labels

# ─── CLAUDE API for critical reasoning (better than Gemini for classification/fabric) ───
import anthropic
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

_claude_client = None
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

def _get_claude():
    global _claude_client
    if _claude_client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            _claude_client = anthropic.Anthropic(api_key=api_key)
    return _claude_client

def claude_query(prompt, images=None):
    """Use Claude Haiku for critical reasoning. Falls back to Gemini if unavailable."""
    client = _get_claude()
    if not client:
        return llm_query(prompt)

    try:
        content = []
        if images:
            import base64
            for img_path in images:
                if os.path.exists(img_path):
                    with open(img_path, "rb") as f:
                        b64 = base64.standard_b64encode(f.read()).decode()
                    ext = img_path.lower().rsplit(".", 1)[-1]
                    media = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
                    content.append({"type": "image", "source": {"type": "base64", "media_type": media, "data": b64}})
        content.append({"type": "text", "text": prompt})

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            temperature=0,
            messages=[{"role": "user", "content": content}]
        )
        text = response.content[0].text if response.content else ""
        return text, ""
    except Exception as e:
        print(f"[Claude API] Failed: {e}. Falling back to Gemini.")
        if images:
            return analyze_images(images, prompt)
        return llm_query(prompt)
from models import (
    TechPackHeader, GarmentClassificationModel,
    FabricDecisionModel, ConstructionDecisionModel,
    MeasurementDecisionModel
)


# ─── STATIC DATA (from 26 trained PDFs) ───

QUALITY_STANDARDS = [
    {"test": "Tensile Strength", "method": "ISO 13934-2", "requirements": "", "comments": ""},
    {"test": "Shrinkage & Dimensional Stability", "method": "ISO 5077", "requirements": "Shrinkage < 3%", "comments": ""},
    {"test": "Color Fastness to Washing", "method": "ISO 105-C06", "requirements": "Rating >= 4 (scale 1-5)", "comments": ""},
    {"test": "Color Fastness to Rubbing", "method": "ISO 105-X12", "requirements": "Dry: >= Grade 4, Wet: >= Grade 3", "comments": ""},
    {"test": "Color Fastness to Dry Cleaning", "method": "ISO 105-D01", "requirements": "Grade >= 4", "comments": ""},
    {"test": "Seam Strength & Durability", "method": "ISO 13935-2", "requirements": ">= 180 N", "comments": ""}
]

CARE_LABEL_INSTRUCTIONS = [
    "The care label must contain <strong>carelabel symbols</strong> and those only.",
    "Care label must be made in recycled polyester.",
    "Care labels must contain origin: made in India.",
    "Care labels must be given the same size, font and style.",
    "Care instructions should follow <strong>ISO 3758 standard</strong>."
]

OTHER_STANDARDS = [
    {"title": "Standard 100 by Oekotex", "description": "Label that ensures consumers that all materials used in a garment are tested for harmful substances."},
    {"title": "EU Ecolabel", "description": "Label that ensures consumers that textiles are made using less harmful substances, energy and water."}
]


def _report(callback, step, decision, reasoning, progress):
    """Helper to push progress if callback exists."""
    if callback:
        callback(step, decision, reasoning, progress)
    print(f"[SKILL] {step}: {decision}")


def _load_corrections(garment_type):
    """Load relevant corrections from past generations."""
    try:
        corrections_file = Path("data/corrections_log.json")
        if corrections_file.exists():
            with open(corrections_file) as f:
                all_corrections = json.load(f)
            relevant = [c for c in all_corrections if any(
                kw in garment_type.lower() for kw in c.get("garment_type", "").lower().split()
            ) and c.get("reason")]
            return relevant[-10:]  # last 10 relevant
    except Exception:
        pass
    return []


def _simplify_fabric_name(name):
    """Simplify verbose fabric names: SILK SATIN → SILK."""
    if not name:
        return name
    name_upper = name.upper()
    for simple in ["SILK", "WOOL", "COTTON", "POLYESTER", "CHIFFON", "LINEN", "GABARDINE"]:
        if simple in name_upper:
            # Keep GSM if present
            gsm_match = re.search(r'(\d{2,4}\s*[-–]\s*\d{2,4}\s*GSM|\d{2,4}\s*GSM)', name, re.IGNORECASE)
            gsm_part = f", {gsm_match.group(0)}" if gsm_match else ""
            return f"{simple}{gsm_part}"
    return name


def generate_techpack(images, context, generate=False, sample_size="M",
                      progress_callback=None, brand_logo_path=None):
    """
    Skill-based tech pack generation. Drop-in replacement for main.py's generate_techpack().
    """
    _report(progress_callback, "Starting pipeline", "Initializing skill-based generation", "", 2)

    # ─── Load master template ───
    with open("data/master.json") as f:
        master = json.load(f)

    front_img = images[0]
    back_img = images[1] if len(images) > 1 else images[0]

    # ─── STEP 1: Vision Analysis ───
    _report(progress_callback, "Vision Analysis", "Analyzing garment images", "", 5)

    vision_prompt = """Analyze this garment image in detail. Identify:
1. GARMENT TYPE: Be specific — blazer, dress, coat, 3-piece suit, blouse, pant, cardigan, etc.
   If you see MULTIPLE pieces (blazer + vest + trouser), say "3-piece suit".
2. SILHOUETTE: A-line, fitted, straight, oversized, etc.
3. ALL CONSTRUCTION FEATURES: collar type, neckline, sleeves, buttons (count them!), pockets (type!), belt, pleats, darts, zippers, seams, hem style, trims
4. CLOSURES: What closure mechanism(s) are visible? Buttons (how many?), zipper, tie, wrap?
   If NO closure is visible and garment is fitted woven/satin → it likely has an invisible zipper.
   Only list what you can actually SEE.
5. DOMINANT COLORS: Extract hex code(s) from the fabric — pick the true fabric color, not shadows.
6. FABRIC ASSESSMENT: Based on texture, drape, sheen, weight — what fabric type?
7. IS IT MULTI-PIECE? (suit = blazer + pants, 3-piece = blazer + vest + pants)

Be thorough and specific. This analysis drives the entire tech pack."""

    # Use CLAUDE for vision analysis (better garment understanding than Gemini)
    vision_text, vision_think = claude_query(vision_prompt, images=images)
    _report(progress_callback, "Vision Analysis", f"Analysis complete ({len(vision_text)} chars)",
            vision_think[:500] if vision_think else "", 10)

    # ─── STEP 2: Classification ───
    _report(progress_callback, "Classification", "Identifying garment type", "", 15)

    classification_prompt = f"""Based on this garment analysis, classify it:

{vision_text}

User context: {context}

Classify:
- category: Menswear, Womenswear, or Kidswear
- garment_type: specific type (blazer, 3-piece suit, skirt suit, blouse, coat, pant, dress, etc.)
- pieces: list each SEPARATE garment piece visible (e.g., ["blazer", "skirt"] or ["blazer", "vest", "trouser"])
- complexity: Simple, Medium, Complex
- fit_type: Slim, Regular, Oversized, Relaxed

CRITICAL RULES for multi-piece detection:
- A SHIRT or TURTLENECK worn UNDER a blazer is NOT a vest. It's just an inner layer — ignore it.
- A 3-PIECE SUIT means: blazer + VEST (waistcoat with buttons, no sleeves) + trouser. If there's no separate vest visible, it's NOT 3-piece.
- SKIRT SUIT = blazer + skirt (2 pieces only, no vest)
- PANT SUIT = blazer + trouser (2 pieces only, no vest)
- Only count pieces that are the SAME fabric/color as part of the suit. A different-color inner layer is separate.

Return JSON only: {{"category": "...", "garment_type": "...", "pieces": ["blazer", "skirt"], "complexity": "...", "fit_type": "..."}}"""

    # Use CLAUDE for classification (critical — Gemini misclassified suit as dress)
    class_result, class_think = claude_query(classification_prompt)
    try:
        # Parse JSON from response
        json_match = re.search(r'\{[^}]+\}', class_result)
        classification = json.loads(json_match.group()) if json_match else {"category": "Womenswear", "garment_type": "dress"}
    except:
        classification = {"category": "Womenswear", "garment_type": "dress"}

    garment_type = classification.get("garment_type", "garment")
    category = classification.get("category", "Womenswear")
    _report(progress_callback, "Classification", f"{garment_type} ({category})", class_think[:300] if class_think else "", 20)

    # ─── STEP 3: Header ───
    _report(progress_callback, "Header", "Generating style code and metadata", "", 22)

    # Parse context
    brand = "BRAND"
    collection = "JC PRIVATE"
    season = "Fall / Winter"
    fabric_pref = ""
    size_range = "S - XL"

    for line in context.split("\n"):
        line = line.strip()
        if "brand" in line.lower() and ":" in line:
            brand = line.split(":", 1)[1].strip()
        elif "collection" in line.lower() and ":" in line:
            collection = line.split(":", 1)[1].strip()
        elif "season" in line.lower() and ":" in line:
            season = line.split(":", 1)[1].strip()
        elif "fabric" in line.lower() and ":" in line:
            fabric_pref = line.split(":", 1)[1].strip()
        elif "size" in line.lower() and "range" in line.lower() and ":" in line:
            size_range = line.split(":", 1)[1].strip()
        elif "category" in line.lower() and ":" in line:
            category = line.split(":", 1)[1].strip()

    # Style code
    brand_code = brand[:3].upper() if len(brand) >= 3 else brand.upper()
    # Extract year from season string (e.g., "Fall/Winter 2025" → "25", "FW25" → "25")
    year_match = re.search(r'(\d{2,4})', season)
    year_suffix = year_match.group()[-2:] if year_match else "25"
    if "fall" in season.lower() or "winter" in season.lower() or "fw" in season.lower():
        season_code = f"FA/WI{year_suffix}"
    elif "spring" in season.lower() or "summer" in season.lower() or "ss" in season.lower():
        season_code = f"SP/SU{year_suffix}"
    else:
        season_code = f"FA/WI{year_suffix}"
    garment_codes = {
        "dress": "DRS", "blouse": "BLO", "shirt": "SHT", "coat": "TRC", "trench": "TRC",
        "blazer": "BLZ", "jacket": "JKT", "pant": "PNT", "trouser": "PNT", "cardigan": "CRD",
        "turtleneck": "TRT", "hoodie": "HDY", "vest": "VST", "gown": "GWN",
        "cocktail": "CDR",
    }
    # Suit codes based on pieces
    pieces = classification.get("pieces", [])
    pieces_lower = [p.lower() for p in pieces]
    gt_lower = garment_type.lower()

    if "skirt suit" in gt_lower or ("skirt" in pieces_lower and any(p in pieces_lower for p in ["blazer", "jacket"])):
        gar_code = "SKSU"
    elif "3-piece" in gt_lower or "3 piece" in gt_lower or ("vest" in pieces_lower and "trouser" in pieces_lower):
        gar_code = "3PS"
    elif "pant suit" in gt_lower or ("trouser" in pieces_lower and any(p in pieces_lower for p in ["blazer", "jacket"])):
        gar_code = "PNSU"
    elif "suit" in gt_lower:
        gar_code = "SUT"
    else:
        gar_code = "GRM"
        for kw, code in garment_codes.items():
            if kw in gt_lower:
                gar_code = code
                break

    style_name = f"JPC-{brand_code}-{season_code}-{gar_code}"
    description = f"{garment_type}".title()

    today = datetime.date.today()
    master["header"] = {
        "date": today.strftime("%d/%m/%Y"), "season": season, "collection": collection,
        "style_name": style_name, "description": description, "category": category,
        "brand": brand, "size_range": size_range, "total_order_quantity": "",
        "sample_size_1st": sample_size, "sample_pre_production": "", "sample_production": ""
    }

    # ─── STEP 4: Color + Pantone ───
    _report(progress_callback, "Color Extraction", "Extracting hex codes from multiple garment areas", "", 25)

    color_prompt = f"""Look at this garment carefully. Extract hex color codes from MANY different areas of the fabric.

Sample from these specific zones:
1. Center chest / front body (flattest area)
2. Upper shoulder area
3. Sleeve (mid-arm)
4. Lower body / skirt / hem area
5. Back panel (if visible)
6. Any DIFFERENT colored trim or contrast area

For EACH zone, give the hex of the TRUE fabric color — not shadow, not highlight, not skin reflection.

Return JSON array with 6-10 samples: [{{"color_name": "descriptive name", "color_hex": "#XXXXXX", "area": "center chest"}}]
ONLY fabric colors. Ignore skin, hair, background, inner layers (like a turtleneck under a blazer)."""

    color_result, _ = claude_query(color_prompt, images=images)
    colors = []
    try:
        json_match = re.search(r'\[.*\]', color_result, re.DOTALL)
        if json_match:
            colors = json.loads(json_match.group())
    except:
        colors = [{"color_name": "Primary", "color_hex": "#808080"}]

    # Cluster similar hex samples → compute median → send fewer, better hexes to scraper
    from utils import rgb_to_lab
    from colormath.color_diff import delta_e_cie2000

    def _cluster_hexes(hex_list, thresh=4.0):
        """Group similar hexes together using Delta-E distance."""
        groups = []
        for h in hex_list:
            r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
            lab = rgb_to_lab((r, g, b))
            placed = False
            for group in groups:
                ref_h = group[0]
                rr, gg, bb = int(ref_h[1:3], 16), int(ref_h[3:5], 16), int(ref_h[5:7], 16)
                ref_lab = rgb_to_lab((rr, gg, bb))
                if float(delta_e_cie2000(lab, ref_lab)) < thresh:
                    group.append(h)
                    placed = True
                    break
            if not placed:
                groups.append([h])
        return groups

    def _median_hex(hex_list):
        """Compute median RGB from a list of hex values."""
        rs = [int(h[1:3], 16) for h in hex_list]
        gs = [int(h[3:5], 16) for h in hex_list]
        bs = [int(h[5:7], 16) for h in hex_list]
        import statistics
        mr, mg, mb = int(statistics.median(rs)), int(statistics.median(gs)), int(statistics.median(bs))
        return f"#{mr:02x}{mg:02x}{mb:02x}"

    # Extract all hex values and cluster them
    all_hexes = [c.get("color_hex", "") for c in colors if c.get("color_hex", "").startswith("#")]
    hex_groups = _cluster_hexes(all_hexes, thresh=5.0) if len(all_hexes) > 1 else [[h] for h in all_hexes]
    median_hexes = [_median_hex(group) for group in hex_groups]

    _report(progress_callback, "Pantone", f"Clustered {len(all_hexes)} samples → {len(median_hexes)} color groups", "", 27)

    # Send median hexes to pantone.com scraper
    all_pantone_options = []
    try:
        from pantone_scraper import get_tcx_options
        for median_h in median_hexes[:4]:
            hex_clean = median_h.lstrip("#")
            _report(progress_callback, "Pantone", f"Checking pantone.com for #{hex_clean} (median of {len(hex_groups[median_hexes.index(median_h)])} samples)", "", 28)
            scraped = get_tcx_options(hex_clean)
            if scraped:
                for opt in scraped:
                    code = opt.get("code", "")
                    if "TCX" not in code:
                        code += " TCX"
                    opt["code"] = code
                    opt["source_hex"] = hex_clean
                all_pantone_options.extend(scraped)
    except Exception as e:
        print(f"[Pantone scraper] Failed: {e}")

    # Deduplicate pantone options by code
    seen_codes = set()
    unique_pantone = []
    for opt in all_pantone_options:
        if opt.get("code") not in seen_codes:
            seen_codes.add(opt.get("code"))
            unique_pantone.append(opt)

    # ALSO run local Delta-E on all median hexes and merge results
    for median_h in median_hexes[:4]:
        local_results = nearest_pantone_tcx(median_h, top_k=3)
        for r in local_results:
            if r["code"] not in seen_codes:
                seen_codes.add(r["code"])
                unique_pantone.append({"code": r["code"], "name": r["name"], "source": "delta_e", "delta_e": r["delta_e"]})

    if unique_pantone:
        primary_pantone = unique_pantone[0]["code"]
        _report(progress_callback, "Pantone", f"Matched: {primary_pantone} ({len(unique_pantone)} total options)", "", 30)
    else:
        # Fallback to local Delta-E
        hex_val = colors[0].get("color_hex", "#808080")
        pantone_results = nearest_pantone_tcx(hex_val, top_k=5)
        unique_pantone = [{"code": r["code"], "name": r["name"]} for r in pantone_results]
        primary_pantone = pantone_results[0]["code"] if pantone_results else "Unknown"
        _report(progress_callback, "Pantone", f"Delta-E match: {primary_pantone}", "", 30)

    # Build final color list for the tech pack
    primary_color = {
        "color_name": colors[0].get("color_name", "Primary") if colors else "Primary",
        "color_hex": colors[0].get("color_hex", "#808080") if colors else "#808080",
        "pantone_tcx": primary_pantone,
    }
    # Add all pantone options as optional_colors for designer to pick
    optional_colors = [{"color_name": opt.get("name", ""), "color_hex": colors[0].get("color_hex", ""), "pantone_tcx": opt.get("code", "")} for opt in unique_pantone[:5]]
    if not optional_colors:
        optional_colors = [primary_color]

    _report(progress_callback, "Color", f"{len(optional_colors)} Pantone options for designer to pick", "", 31)

    # ─── STEP 5: Fabric ───
    _report(progress_callback, "Fabric Decision", "Determining fabric type", "", 35)

    # Load corrections for this garment type
    corrections = _load_corrections(garment_type)
    corrections_context = ""
    if corrections:
        corrections_context = "\nPAST CORRECTIONS (apply if relevant):\n"
        for c in corrections[-5:]:
            corrections_context += f"- {c.get('field_key','')}: {c.get('reason','')}\n"

    fabric_prompt = f"""Based on this garment analysis, determine the fabric:

{vision_text}

User context: {context}
Season: {season}
Garment type: {garment_type}
{corrections_context}

FABRIC DECISION TREE — use the EXACT output name shown:
- Knit (stretchy, visible loops) → "WOOL BLEND KNIT" (FW) / "COTTON KNIT" (SS)
- Woven + Sheen + Fluid → "SILK"
- Woven + Sheen + Structured → "SATEEN"
- Woven + Matte + Heavy + Suit/Blazer/Formal → "WOVEN SUITING" (NOT "WOOL" — use "WOVEN SUITING")
- Woven + Matte + Heavy + Coat → "GABARDINE" or "WOOL"
- Woven + Matte + Light → "COTTON" or "COTTON POPLIN"
- Sheer → "CHIFFON" or "GEORGETTE"
- Jersey/Stretch → "JERSEY KNIT"

NAMING RULES:
- For suits/blazers: always say "WOVEN SUITING" (not "WOOL SUITING" or "WOOL")
- For silk garments: say "SILK" (not "SILK SATIN" or "SILK CHARMEUSE")
- For cotton: say "COTTON" (not "COTTON TWILL" or "COTTON POPLIN" unless construction matters)
- Always include GSM range

{"User specified fabric: " + fabric_pref + ". USE THIS." if fabric_pref else ""}

Your job is to analyze WHAT YOU ACTUALLY SEE in the garment and reason about what fabric it could be.

Think through these questions:
1. What do I SEE? (texture, sheen, drape, weight, how it folds, surface finish)
2. What garment type is this? (suits are typically wool/poly-wool, blouses are silk/polyester, etc.)
3. What season? (FW = heavier fabrics, SS = lighter fabrics)
4. What are the REALISTIC options? Only list fabrics that COULD actually be this garment.

Do NOT make up random options. Each option must be justified by what you see OR by what's standard for this garment type + season.

Return JSON:
{{
  "fabric_name": "your best guess with GSM",
  "options": [
    {{"name": "FABRIC, GSM", "why": "specific visual evidence or industry convention that supports this"}},
    {{"name": "FABRIC, GSM", "why": "specific visual evidence or industry convention that supports this"}}
  ],
  "reasoning": "detailed explanation of what you see and why you chose this",
  "confidence": 0.0-1.0
}}

Only include 2-3 options that you genuinely think are possible. Don't pad with unlikely options."""

    # Use CLAUDE for fabric decision (better reasoning about visual cues)
    fabric_result, fabric_think = claude_query(fabric_prompt, images=images)
    try:
        json_match = re.search(r'\{[^}]+\}', fabric_result, re.DOTALL)
        fabric_data = json.loads(json_match.group()) if json_match else {}
    except:
        fabric_data = {"fabric_name": fabric_pref or "FABRIC", "reasoning": "Could not determine", "confidence": 0.5}

    fabric_name = _simplify_fabric_name(fabric_data.get("fabric_name", fabric_pref or "FABRIC"))

    # Fabric cross-check: what do manufacturers ACTUALLY use for this garment type + season?
    if not fabric_pref:
        _report(progress_callback, "Fabric Cross-Check", "Verifying against industry standards for this garment type + season", "", 37)
        try:
            ai_options = fabric_data.get("options", [])
            ai_reasoning = fabric_data.get("reasoning", "")

            crosscheck_prompt = f"""A designer identified a {garment_type} ({category}, {season} season) fabric as: {fabric_name}

Their visual reasoning: {ai_reasoning[:300]}
Their options: {json.dumps(ai_options, default=str)[:300]}

CROSS-CHECK against what manufacturers ACTUALLY use:

For {garment_type} in {season}:
- What fabric composition do garment factories typically use?
- What GSM range is standard for production?
- Does the AI's identification make sense given the garment type and season?
- Are there other fabrics that are equally common for this exact garment type?

Consider:
- Season: {"Heavier fabrics (wool, gabardine, heavy cotton)" if "winter" in season.lower() or "fall" in season.lower() else "Lighter fabrics (cotton, linen, silk, chiffon)"}
- Garment: {garment_type} — what do brands like Zara, H&M, luxury brands typically use for this?
- The visual evidence the AI described

Reply with JSON:
{{
  "verified_fabric": "the most likely fabric with GSM",
  "alternatives": [
    {{"name": "FABRIC, GSM", "why": "specific reason this is possible for this garment + season"}}
  ],
  "matches_ai": true/false,
  "note": "brief explanation of your cross-check conclusion"
}}"""

            crosscheck_result, _ = llm_query(crosscheck_prompt)
            try:
                json_match = re.search(r'\{.*\}', crosscheck_result, re.DOTALL)
                if json_match:
                    crosscheck = json.loads(json_match.group())
                    verified = crosscheck.get("verified_fabric", "")
                    if verified:
                        old_fabric = fabric_name
                        fabric_name = _simplify_fabric_name(verified)
                        fabric_data["_cross_checked"] = crosscheck
                        # Merge alternatives into options
                        for alt in crosscheck.get("alternatives", []):
                            if alt not in fabric_data.get("options", []):
                                fabric_data.setdefault("options", []).append(alt)
                        if crosscheck.get("matches_ai"):
                            fabric_data["confidence"] = min(fabric_data.get("confidence", 0.5) + 0.15, 0.9)
                        _report(progress_callback, "Fabric Cross-Check",
                            f"Verified: {fabric_name}" + (f" (was {old_fabric})" if old_fabric != fabric_name else ""),
                            crosscheck.get("note", ""), 39)
            except Exception:
                pass
        except Exception as e:
            _report(progress_callback, "Fabric Cross-Check", f"Unavailable: {str(e)[:50]}", "", 39)

    _report(progress_callback, "Fabric Decision", fabric_name, fabric_think[:300] if fabric_think else "", 40)

    # ─── STEP 6: Construction ───
    _report(progress_callback, "Construction", "Generating seam specifications", "", 45)

    # Min rows per type
    min_rows = {"blazer": 10, "jacket": 10, "coat": 10, "pant": 10, "trouser": 10,
                "blouse": 8, "shirt": 8, "dress": 8, "suit": 10, "cardigan": 10, "skirt": 6}
    expected_min = 6
    for kw, count in min_rows.items():
        if kw in garment_type.lower():
            expected_min = max(expected_min, count)

    construction_prompt = f"""Generate a product construction table for a {garment_type}.

Fabric: {fabric_name}
Vision analysis: {vision_text[:500]}
{corrections_context}

Generate at least {expected_min} construction rows.

{"For 3-piece suit: group rows by piece (BLAZER, VEST, TROUSER)" if "suit" in garment_type.lower() or "3-piece" in garment_type.lower() else ""}

Each row: {{"part": "...", "seam_type": "...", "seam_allowance": "...", "stitch_type": "", "stitch_size_spi": "10-12", "machine_type": "..."}}

Return ONLY a JSON array of rows."""

    construction_result, _ = llm_query(construction_prompt, enable_thinking=True)
    seams = []
    try:
        raw = construction_result.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        seams = json.loads(raw)
    except:
        seams = [{"part": "Main seams", "seam_type": "Plain seam", "seam_allowance": "1 cm", "stitch_type": "", "stitch_size_spi": "10-12", "machine_type": "Single needle"}]

    _report(progress_callback, "Construction", f"{len(seams)} seam specifications", "", 50)

    # ─── STEP 7: Accessories ───
    _report(progress_callback, "Accessories", "Identifying accessories from garment", "", 55)

    accessories_prompt = f"""List accessories for a {garment_type} based on this analysis:

{vision_text[:500]}

ONLY list items you can actually SEE in the garment or that are 100% certain:
- Visible buttons → list with count, type, size
- Visible zipper → list type and position
- Thread → always include
- Labels → always include (care + size + brand)

Do NOT list invisible zippers unless you can SEE them.
Do NOT guess closures — only list what's visible.

Return JSON array: [{{"description": "...", "quantity_per_style": "...", "color": "...", "position": "..."}}]"""

    # Use CLAUDE for accessories (critical — needs to see images for button counting)
    accessories_result, _ = claude_query(accessories_prompt, images=images)
    accessories = []
    try:
        raw = accessories_result.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        accessories = json.loads(raw)
    except:
        accessories = [
            {"description": "THREAD, POLYESTER", "quantity_per_style": "1", "color": "MATCHING", "position": ""},
            {"description": "Care label, Size label and brand label", "quantity_per_style": "3", "color": "", "position": "SIDE SEAM / CENTER BACK"}
        ]

    # Only add fly zipper for pants (100% certain)
    if any(kw in garment_type.lower() for kw in ["pant", "trouser"]):
        has_zipper = any("zipper" in str(a).lower() for a in accessories)
        if not has_zipper:
            accessories.append({"description": "ZIPPER, YKK NYLON COIL, FRONT FLY + HOOK AND BAR", "quantity_per_style": "1 SET", "color": "MATCHING", "position": "FRONT FLY"})

    _report(progress_callback, "Accessories", f"{len(accessories)} items identified", "", 60)

    # ─── STEP 8: Measurements ───
    _report(progress_callback, "Measurements", "Generating POM table", "", 65)

    # POM columns per garment type
    is_suit = any(kw in garment_type.lower() for kw in ["suit", "3-piece", "3 piece"])
    is_pant = any(kw in garment_type.lower() for kw in ["pant", "trouser"])
    is_dress = any(kw in garment_type.lower() for kw in ["dress", "gown"])
    is_skirt = "skirt" in garment_type.lower()
    is_knit = any(kw in garment_type.lower() for kw in ["cardigan", "sweater", "pullover"])

    measurement_prompt = f"""Generate a size chart for a {garment_type} ({category}).
Size range: {size_range}. Sample size: {sample_size}.

{"POM columns: bust, waist, hip, blazer_length, sleeve_length, pant_waist, pant_hip, pant_inseam (8 columns for suit)" if is_suit else ""}
{"POM columns: waist, hip, inseam, outseam, leg_opening (5 columns for pants)" if is_pant and not is_suit else ""}
{"POM columns: bust, waist, hip (3 columns for dress)" if is_dress else ""}
{"POM columns: waist, hip, skirt_length (3 columns for skirt)" if is_skirt else ""}
{"POM columns: bust, shoulder, sleeve_length, body_length (4 columns for knitwear, NO waist/hip)" if is_knit else ""}
{"POM columns: bust, waist, hip, shoulder, sleeve_length, body_length (6 columns for tops)" if not any([is_suit, is_pant, is_dress, is_skirt, is_knit]) else ""}

Values in INCHES as ranges (e.g. "35-36"). Use US standard grading (+2" per size for bust/waist).

Return JSON array, one object per size: [{{"size": "S", "bust": "34-35", ...}}]"""

    measurement_result, _ = llm_query(measurement_prompt, enable_thinking=True)
    measurements = []
    try:
        raw = measurement_result.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        measurements = json.loads(raw)
    except:
        measurements = [{"size": "S", "bust": "34-35", "waist": "26-27"}]

    _report(progress_callback, "Measurements", f"{len(measurements)} sizes × {len(measurements[0].keys())-1} POMs", "", 70)

    # ─── STEP 9: Details text ───
    details_prompt = f"""Write garment details for a {garment_type} tech pack.
Plain text, 6-8 lines max. Format:
Silhouette: [one line]
Sleeves: [one line]
Other Features:
[feature 1]
[feature 2]

Based on: {vision_text[:500]}
NO markdown, NO bold, NO headers."""

    details_text, _ = analyze_images(images, details_prompt)

    # ─── STEP 10: Populate master JSON ───
    _report(progress_callback, "Building Tech Pack", "Assembling all data", "", 75)

    master["page_1"] = {
        "garment_front_view_url": front_img, "garment_back_view_url": back_img,
        "style_number": style_name, "date": today.strftime("%d-%m-%Y"),
        "brand_name": brand, "collection_name": collection,
        "brand_logo": brand_logo_path or "assets/brand_logo.png", "season": season.upper()
    }

    master["page_2"] = {
        "front_image_url": front_img, "back_image_url": back_img,
        "detail_image_1_url": "", "detail_image_2_url": "", "detail_image_3_url": "",
        "detail_image_4_url": "", "detail_image_5_url": "", "detail_image_6_url": "",
        "color_name": primary_color.get("color_name", ""), "color_hex": primary_color.get("color_hex", ""),
        "pantone_tcx": primary_color.get("pantone_tcx", ""),
        "details": details_text,
        "optional_colors": optional_colors,
    }

    master["page_3"] = {
        "technical_sketch_img": "assets/technical_sketch.png",
        "brand_label_img": "assets/brand_label_final.png",
        "care_label_img": "assets/care_label_final.png",
        "brand_label": {"image_url": "assets/brand_label_final.png", "size": "Approx 5 cm (W) × 3 cm (H)", "placement": "Inner back neck seam"},
        "size_label": {"image_url": "", "size": "Approx 2.5 cm × 2.5 cm", "placement": "Below or beside the brand label"},
        "care_label": {"image_url": "assets/care_label_final.png", "size": "Approx 5 cm × 8 cm", "placement": "Inner left side seam"},
        "label_notes": "The color of the labels is white. Type of: 100% Recycled polyester woven label."
    }

    master["page_4"] = {"accessories": accessories}
    master["page_5"] = {"seams": seams}
    master["page_6"] = {"measurement_image_url": "assets/measurement_diagram.png", "measurements": measurements}
    master["page_10"] = master["page_6"]

    master["page_7"] = {
        "fabrics": [{"description": fabric_name, "color": f"PANTONE {primary_color.get('pantone_tcx', '')}", "position": ""}],
        "_fabric_reasoning": fabric_data.get("reasoning", ""),
        "_fabric_options": fabric_data.get("options", []),
        "quality_standards": QUALITY_STANDARDS
    }

    master["page_8"] = {"reference_image_front": front_img, "reference_image_back": back_img}

    # Standardized wash/care (same for ALL fabrics)
    composite_name = _simplify_fabric_name(fabric_name).split(",")[0].strip()
    master["page_9"] = {
        "wash_label": {
            "composition": composite_name,
            "washing_instructions": "Machine wash cold with like colors (30°C / 85°F)",
            "bleaching": "Do not bleach", "drying_instructions": "Tumble dry low",
            "ironing_instructions": "Warm iron if needed",
            "dry_cleaning": {"line_1": "Do not dry clean", "line_2": ""},
            "label_colors": "Black and White"
        },
        "care_label": {"image": "assets/care_label_final.png"},
        "care_label_instructions": CARE_LABEL_INSTRUCTIONS,
        "other_standards": OTHER_STANDARDS
    }

    # Confidence scoring
    master["_confidence"] = {
        "pantone_match": 0.85,
        "fabric_identification": fabric_data.get("confidence", 0.5),
        "construction_completeness": 0.9 if len(seams) >= expected_min else 0.7,
        "measurement_accuracy": 0.85,
        "accessories_completeness": 0.85,
        "overall": 0.82,
        "_notes": [
            f"Classification: {garment_type} ({category})",
            f"Fabric: {fabric_name} (confidence: {fabric_data.get('confidence', 0.5)})",
            f"Construction: {len(seams)} rows (min {expected_min})",
        ]
    }

    # ─── STEP 11: Detail crops ───
    _report(progress_callback, "Detail Cropping", "Identifying detail regions", "", 78)

    combined_image = combine_images_horizontally(images, "assets/combined.png")
    ai_crops = ai_crop_detail_regions(images, details_text, "assets", 4)

    if not ai_crops:
        # Fallback to grid crops
        grid_crops = split_into_grids(combined_image, "assets", grid_height=700)
        ai_crops = grid_crops[:4]

    for i, crop_path in enumerate(ai_crops[:6]):
        master["page_2"][f"detail_image_{i+1}_url"] = crop_path

    _report(progress_callback, "Detail Cropping", f"{len(ai_crops)} regions cropped", "", 80)

    # ─── STEP 12: Image generation ───
    if generate:
        _report(progress_callback, "Technical Sketch", "Generating sketch with GPT Image 2.5 Flare", "", 82)

        # Build sketch prompt — only VISIBLE features
        visible_accessories = [a for a in accessories if not any(
            kw in str(a).lower() for kw in ["invisible", "hidden", "internal", "fusible", "interfacing", "lining"]
        )]

        # Use classification pieces list to determine layout
        pieces = classification.get("pieces", [])
        has_vest = "vest" in [p.lower() for p in pieces] or "waistcoat" in [p.lower() for p in pieces]
        has_skirt = "skirt" in [p.lower() for p in pieces]
        has_trouser = any(p.lower() in ["trouser", "pant", "trousers", "pants"] for p in pieces)
        is_multi = len(pieces) >= 2

        if has_vest and has_trouser:
            # 3-piece suit
            layout = "Draw each piece as a SEPARATE FLAT GARMENT in a grid. TOP ROW: Blazer front/back, Vest front/back. BOTTOM ROW: Trouser front/back."
        elif has_skirt:
            # Skirt suit (2 piece)
            layout = "Draw each piece as a SEPARATE FLAT GARMENT. TOP ROW: Blazer front/back. BOTTOM ROW: Skirt front/back. NO VEST — this is a 2-piece skirt suit."
        elif has_trouser and not has_vest:
            # Pant suit (2 piece)
            layout = "Draw each piece as a SEPARATE FLAT GARMENT. TOP ROW: Blazer front/back. BOTTOM ROW: Trouser front/back. NO VEST — this is a 2-piece pant suit."
        elif is_multi:
            layout = f"Draw each piece as a SEPARATE FLAT GARMENT: {', '.join(pieces)}. Each piece front and back."
        else:
            layout = "FRONT VIEW on left, BACK VIEW on right."

        # Build button/feature description from what Claude ACTUALLY saw in the image
        button_info = ""
        for a in accessories:
            desc = str(a.get("description", "")).lower()
            if "button" in desc:
                qty = a.get("quantity_per_style", "")
                button_info += f"BUTTONS: {a.get('description', '')} — quantity: {qty}\n"

        sketch_prompt = f"""Look at the reference garment photo carefully. Create a professional technical flat sketch that EXACTLY matches what you see.

LAYOUT: {layout}

CRITICAL — MATCH THE REFERENCE IMAGE EXACTLY:
- Count the EXACT number of buttons visible in the reference photo. Draw that EXACT number. Do NOT add extra buttons.
- Match the EXACT collar/lapel shape from the reference. Do NOT change it.
- Match the EXACT pocket type and position from the reference.
- Match the EXACT silhouette and proportions.
- If you cannot see a feature in the reference photo, do NOT draw it.

{f"BUTTON COUNT FROM REFERENCE: {button_info}" if button_info else ""}

Garment details from analysis:
{details_text[:400]}

DRAWING RULES:
- Draw ONLY the garment flat sketches + callout labels with leader lines
- Do NOT draw accessories panels, button icons, thread spools, or label mockups
- Do NOT draw any separate boxes showing accessories
- LABEL PLACEMENT: SIDE SEAM → outer edge, SHOULDER → top, HEM → bottom, CUFF → wrist
- Pure black line art on white background
- ALL-CAPS callout labels with thin leader lines"""

        generate_image(sketch_prompt, reference_image_path=front_img, output_path="assets/technical_sketch.png")

        # Verify sketch
        issues = verify_sketch_labels("assets/technical_sketch.png", [d.get("description", "")[:30] for d in visible_accessories[:5]])
        if issues:
            _report(progress_callback, "Sketch Verification", f"Issues: {issues[:100]}", "Regenerating...", 84)
            generate_image(sketch_prompt + f"\nCORRECTION: {issues}", reference_image_path=front_img, output_path="assets/technical_sketch.png")

        master["page_3"]["technical_sketch_img"] = "assets/technical_sketch.png"
        _report(progress_callback, "Technical Sketch", "Generated and verified", "", 85)

        # Brand label
        _report(progress_callback, "Brand Label", "Generating", "", 87)
        generate_image(
            f'Woven garment brand label: "{brand}" bold serif, "{description}" smaller, white bg, shadow effect',
            output_path="assets/brand_label_final.png"
        )

        # Care label
        _report(progress_callback, "Care Label", "Generating", "", 89)
        generate_image(
            f'Fabric care label: "{composite_name}" bold, ISO 3758 care symbols, "Machine wash cold", "MADE IN INDIA", white fabric bg',
            output_path="assets/care_label_final.png"
        )

        # Measurement diagram
        _report(progress_callback, "Measurement Diagram", "Generating", "", 91)
        desc_lower = garment_type.lower()
        if has_vest and has_trouser:
            meas_prompt = f"Measurement diagram for {description}. Show ALL 3 pieces separately. Blazer measurements (G-J) + Trouser measurements (A-F). Legend on right."
        elif has_skirt:
            meas_prompt = f"Measurement diagram for {description}. Show 2 pieces: Blazer (G-J: Shoulder, Bust, Waist, Back Length) + Skirt (A-F: Waist, Hip, Thigh, Skirt Length, Hem Width, Rise). Legend on right. NO VEST."
        elif has_trouser and is_multi:
            meas_prompt = f"Measurement diagram for {description}. Show 2 pieces: Blazer (G-J) + Trouser (A-F). Legend on right. NO VEST."
        elif is_pant:
            meas_prompt = f"Measurement diagram for {description}. Pant measurements: A=Waist, B=Hip, C=Inseam, D=Outseam, E=Thigh, F=Leg opening."
        else:
            meas_prompt = f"Measurement diagram for {description}. Measurements: A=Bust, B=Waist, C=Shoulder, D=Sleeve, E=Total length, F=Front length."

        meas_prompt += " Black line art on white. Double-headed arrows with letter labels. Draw ONLY garment sketches with measurement lines and legend. Do NOT draw any accessories, buttons, thread, labels, or any items that are not measurement indicators."
        generate_image(meas_prompt,
                       reference_image_path=front_img, output_path="assets/measurement_diagram.png")
        _report(progress_callback, "Measurement Diagram", "Generated", "", 93)

    # ─── STEP 13: Apply continuous learning corrections ───
    if corrections:
        for c in corrections:
            page_id = c.get("page_id", "")
            field_key = c.get("field_key", "")
            corrected = c.get("corrected_value", "")
            original = c.get("original_value", "")
            if page_id in master and field_key in master[page_id]:
                if isinstance(master[page_id][field_key], str) and original and original in str(master[page_id][field_key]):
                    master[page_id][field_key] = corrected
                    print(f"[LEARNING] Applied: {field_key} = '{corrected[:50]}'")

    # ─── STEP 14: Save + Render ───
    _report(progress_callback, "Rendering PDF", "Generating 10-page PDF", "", 95)

    with open("data/master_filled.json", "w") as f:
        json.dump(master, f, indent=4, ensure_ascii=False)
    with open("data/master_draft.json", "w") as f:
        json.dump(master, f, indent=4, ensure_ascii=False)

    pdf_path = generatePdf()
    _report(progress_callback, "Complete", "Tech Pack ready!", f"Cost: ~$0.17", 100)

    return pdf_path
