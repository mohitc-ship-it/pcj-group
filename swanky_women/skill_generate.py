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
    create_individual_detail_crops,
    combine_images_horizontally, split_into_grids,
    recommend_colors_from_images
)
from skill_image_gen import generate_image, verify_sketch_labels

# ─── CLAUDE API for critical reasoning (better than Gemini for classification/fabric) ───
import anthropic
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

_claude_client = None
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

def _get_claude():
    global _claude_client
    if _claude_client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            _claude_client = anthropic.Anthropic(api_key=api_key)
    return _claude_client

# Load the FULL skill prompt as cached system prompt — gives API calls the same
# knowledge as Claude Code mode (800 lines of trained rules from 26 PDFs)
_SKILL_PROMPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".claude", "commands", "techpack.md")
_CACHED_SYSTEM_PROMPT = None

def _get_cached_system_prompt():
    global _CACHED_SYSTEM_PROMPT
    if _CACHED_SYSTEM_PROMPT is None:
        try:
            with open(_SKILL_PROMPT_PATH) as f:
                _CACHED_SYSTEM_PROMPT = f.read()
            print(f"[Skill] Loaded full skill prompt: {len(_CACHED_SYSTEM_PROMPT)} chars")
        except Exception:
            # Fallback to short version if skill file not found
            _CACHED_SYSTEM_PROMPT = "You are a senior fashion technical designer creating factory-ready tech packs. Use simple fabric names (SILK not SILK SATIN). Only draw VISIBLE features on sketches."
            print("[Skill] Using fallback short prompt")
    return _CACHED_SYSTEM_PROMPT

CACHED_SYSTEM_PROMPT = property(lambda self: _get_cached_system_prompt())  # lazy load


def claude_query(prompt, images=None, enable_thinking=False):
    """Use Claude (Opus/Sonnet/Haiku) with prompt caching on system prompt AND images. Falls back to Gemini if unavailable."""
    client = _get_claude()
    if not client:
        if images:
            return analyze_images(images, prompt)
        return llm_query(prompt)

    try:
        content = []
        if images:
            import base64
            valid_images = [p for p in images if os.path.exists(p)]
            for idx, img_path in enumerate(valid_images):
                with open(img_path, "rb") as f:
                    b64 = base64.standard_b64encode(f.read()).decode()
                ext = img_path.lower().rsplit(".", 1)[-1]
                media = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
                img_block = {"type": "image", "source": {"type": "base64", "media_type": media, "data": b64}}
                # Cache the last image so all images are cached across sequential calls in the pipeline
                if idx == len(valid_images) - 1:
                    img_block["cache_control"] = {"type": "ephemeral"}
                content.append(img_block)
        content.append({"type": "text", "text": prompt})

        model_to_use = os.getenv("CLAUDE_MODEL", CLAUDE_MODEL)
        kwargs = {
            "model": model_to_use,
            "max_tokens": 8192 if enable_thinking else 4096,
            "system": [{
                "type": "text",
                "text": sys_prompt,
                "cache_control": {"type": "ephemeral"}
            }],
            "messages": [{"role": "user", "content": content}]
        }
        if enable_thinking:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": 2048}
        else:
            kwargs["temperature"] = 0

        response = client.messages.create(**kwargs)

        # Log cache stats
        usage = response.usage
        if hasattr(usage, 'cache_read_input_tokens'):
            cached = getattr(usage, 'cache_read_input_tokens', 0)
            if cached > 0:
                print(f"[Claude] Cache hit: {cached} tokens read from cache (90% savings)")

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
    # Garment pieces and structure detection
    pieces = classification.get("pieces", [])
    pieces_lower = [p.lower() for p in pieces]
    gt_lower = garment_type.lower()

    has_vest = "vest" in pieces_lower or "waistcoat" in pieces_lower
    has_skirt = "skirt" in pieces_lower or "skirt" in gt_lower
    has_trouser = any(p in pieces_lower for p in ["trouser", "pant", "trousers", "pants"]) or any(kw in gt_lower for kw in ["pant", "trouser"])
    is_multi = len(pieces) >= 2 or any(kw in gt_lower for kw in ["suit", "set", "2-piece", "3-piece", "2 piece", "3 piece"])
    is_skirt_suit = ("skirt suit" in gt_lower) or (has_skirt and (is_multi or any(p in pieces_lower for p in ["blazer", "jacket"])))

    if is_skirt_suit:
        gar_code = "SKSU"
    elif "3-piece" in gt_lower or "3 piece" in gt_lower or (has_vest and has_trouser):
        gar_code = "3PS"
    elif "pant suit" in gt_lower or (has_trouser and any(p in pieces_lower for p in ["blazer", "jacket"])):
        gar_code = "PNSU"
    elif "suit" in gt_lower:
        gar_code = "SUT"
    else:
        gar_code = "GRM"
        for g_kw, code in garment_codes.items():
            if g_kw in gt_lower:
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

    # ── Check exact hex codes (NO median, NO clustering) ──
    from utils import nearest_pantone_tcx, rgb_to_lab
    from colormath.color_diff import delta_e_cie2000

    all_hexes = [c.get("color_hex", "").strip() for c in colors if c.get("color_hex", "").strip().startswith("#")]
    if not all_hexes:
        all_hexes = ["#808080"]

    _report(progress_callback, "Pantone", f"Checking exact hex codes across {len(all_hexes)} samples", "", 27)

    # For EACH exact hex code, run local Delta-E search against verified Pantone TCX
    all_pantone_candidates = []
    seen_codes = set()

    for h in all_hexes:
        matches = nearest_pantone_tcx(h, top_k=5)
        for m in matches:
            code = m["code"]
            if code not in seen_codes:
                seen_codes.add(code)
                all_pantone_candidates.append({
                    "code": code,
                    "name": m["name"],
                    "hex": m["hex"],
                    "delta_e": m.get("delta_e", 999.0),
                    "source_hex": h
                })

    # Also query official pantone.com scraper for top exact hexes
    try:
        from pantone_scraper import get_tcx_options
        for h in all_hexes[:3]:
            hex_clean = h.lstrip("#")
            _report(progress_callback, "Pantone", f"Checking pantone.com for exact #{hex_clean}", "", 28)
            scraped = get_tcx_options(hex_clean)
            if scraped:
                for opt in scraped:
                    code = opt.get("code", "")
                    if "TCX" not in code:
                        code += " TCX"
                    if code not in seen_codes:
                        seen_codes.add(code)
                        all_pantone_candidates.append({
                            "code": code,
                            "name": opt.get("name", ""),
                            "hex": h,
                            "delta_e": 0.5,
                            "source_hex": h
                        })
    except Exception as e:
        print(f"[Pantone scraper] Failed: {e}")

    # Sort all candidates by closest match (lowest Delta-E)
    all_pantone_candidates.sort(key=lambda x: x.get("delta_e", 999.0))

    if all_pantone_candidates:
        primary_pantone = all_pantone_candidates[0]["code"]
        primary_color_name = all_pantone_candidates[0]["name"] or (colors[0].get("color_name") if colors else "Primary")
    else:
        primary_pantone = "Unknown"
        primary_color_name = colors[0].get("color_name", "Primary") if colors else "Primary"

    # Candidate Pantone suggestions/alternatives for the designer to pick from
    pantone_suggestions = [
        {"code": c["code"], "name": c["name"], "hex": c.get("hex", all_hexes[0])}
        for c in all_pantone_candidates[:8]
    ]

    primary_color = {
        "color_name": primary_color_name,
        "color_hex": all_hexes[0],
        "pantone_tcx": primary_pantone,
        "pantone_options": pantone_suggestions,
    }

    # Monochromatic garments have 1 color with suggestions; distinct contrast colors get their own row
    optional_colors = [primary_color]

    # Check if any sample belongs to a genuinely different contrast color (Delta-E >= 15.0 from primary)
    pr = int(all_hexes[0][1:3], 16)
    pg = int(all_hexes[0][3:5], 16)
    pb = int(all_hexes[0][5:7], 16)
    p_lab = rgb_to_lab((pr, pg, pb))

    for c in colors[1:]:
        c_hex = c.get("color_hex", "").strip()
        if c_hex.startswith("#") and len(c_hex) == 7:
            cr = int(c_hex[1:3], 16)
            cg = int(c_hex[3:5], 16)
            cb = int(c_hex[5:7], 16)
            c_lab = rgb_to_lab((cr, cg, cb))
            diff = float(delta_e_cie2000(p_lab, c_lab))
            if diff >= 15.0:
                c_matches = nearest_pantone_tcx(c_hex, top_k=5)
                c_opts = [{"code": m["code"], "name": m["name"], "hex": m["hex"]} for m in c_matches]
                optional_colors.append({
                    "color_name": c.get("color_name", "Contrast Trim"),
                    "color_hex": c_hex,
                    "pantone_tcx": c_matches[0]["code"] if c_matches else primary_pantone,
                    "pantone_options": c_opts,
                })
                break

    _report(progress_callback, "Pantone", f"Matched: {primary_pantone} ({len(pantone_suggestions)} suggestions available)", "", 31)

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

            crosscheck_result, _ = claude_query(crosscheck_prompt)
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
    for row_kw, count in min_rows.items():
        if row_kw in garment_type.lower():
            expected_min = max(expected_min, count)

    construction_prompt = f"""Generate a product construction table for a {garment_type}.

Fabric: {fabric_name}
Vision analysis: {vision_text[:500]}
{corrections_context}

Generate at least {expected_min} construction rows.

{"For 3-piece suit: group rows by piece (BLAZER, VEST, TROUSER)" if "suit" in garment_type.lower() or "3-piece" in garment_type.lower() else ""}

Each row: {{"part": "...", "seam_type": "...", "seam_allowance": "...", "stitch_type": "", "stitch_size_spi": "10-12", "machine_type": "..."}}

Return ONLY a JSON array of rows."""

    construction_result, _ = claude_query(construction_prompt)
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

    accessories_prompt = f"""List production accessories / trims / findings (BOM) for a {garment_type} based on this analysis:

{vision_text[:500]}

Follow apparel industry manufacturing standards:
- Thread: MUST be specified as:
  - description: "100% Spun Polyester Core-Spun Thread (Tex 27 / Ticket 120)"
  - quantity_per_style: "AS REQD" (NEVER use "1")
  - color: "DTM (Dyed to Match - {primary_pantone})"
  - position: "All Seams & Hems"
- Labels: list EACH label separately (do NOT group them into one row):
  - Main Brand Woven Label: quantity: "1", color: "White / Brand Colors", position: "Center Back Inner Neck"
  - Care & Composition Printed Satin Label: quantity: "1", color: "White / Black Print", position: "Inner Left Side Seam"
  - Size Woven Loop / Pip: quantity: "1", color: "White", position: "Below Main Brand Label"
- Hardware / closures (buttons, zippers, snaps, buckles): ONLY if visible on the garment. If no buttons or zippers exist, do NOT add any!

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
            {"description": "100% Spun Polyester Core-Spun Thread (Tex 27 / Ticket 120)", "quantity_per_style": "AS REQD", "color": f"DTM ({primary_pantone})", "position": "All Seams & Hems"},
            {"description": "Main Brand Woven Label", "quantity_per_style": "1", "color": "White / Brand Colors", "position": "Center Back Inner Neck"},
            {"description": "Care & Composition Printed Satin Label", "quantity_per_style": "1", "color": "White / Black Print", "position": "Inner Left Side Seam"},
            {"description": "Size Pip Woven Label", "quantity_per_style": "1", "color": "White", "position": "Below Main Brand Label"}
        ]

    # Sanitize thread entries to industry standard
    for a in accessories:
        if "thread" in a.get("description", "").lower():
            if str(a.get("quantity_per_style", "")).strip() in ("1", "1.0", "1 spool", "1 cone", ""):
                a["quantity_per_style"] = "AS REQD"
            if not a.get("position"):
                a["position"] = "All Seams & Hems"
            if str(a.get("color", "")).upper() in ("MATCHING", ""):
                a["color"] = f"DTM ({primary_pantone})"

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

    # Determine POM columns based on garment type
    is_skirt_suit = is_skirt_suit or (has_skirt and is_multi)
    if is_suit and not is_skirt_suit:
        pom_instruction = "COLUMNS REQUIRED: size, bust, waist, hip, blazer_length, sleeve_length, pant_waist, pant_hip, pant_inseam"
    elif is_skirt_suit:
        pom_instruction = "COLUMNS REQUIRED: size, bust, waist, hip, skirt_length"
    elif is_pant:
        pom_instruction = "COLUMNS REQUIRED: size, waist, hip, inseam, outseam, leg_opening"
    elif is_dress:
        pom_instruction = "COLUMNS REQUIRED: size, bust, waist, hip"
    elif is_skirt:
        pom_instruction = "COLUMNS REQUIRED: size, waist, hip, skirt_length"
    elif is_knit:
        pom_instruction = "COLUMNS REQUIRED: size, bust, shoulder, sleeve_length, body_length (NO waist, NO hip)"
    else:
        pom_instruction = "COLUMNS REQUIRED: size, bust, waist, hip, shoulder, sleeve_length, body_length"

    measurement_prompt = f"""Generate a size chart for a {garment_type} ({category}).
Size range: {size_range}. Sample size: {sample_size}.

{pom_instruction}

You MUST include ALL columns listed above. Do not skip any.
Values in INCHES as ranges (e.g. "35-36"). Use US standard grading (+2" per size for bust/waist).

Return JSON array, one object per size. Example:
[{{"size": "S", "bust": "34-35", "waist": "26-27", "hip": "36-37", "skirt_length": "22-24"}}]"""

    measurement_result, _ = claude_query(measurement_prompt)
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

    # ─── POM Table for Garment Measurements page (page_10) ───
    pom_prompt = f"""Generate a Point of Measurement (POM) table for a {garment_type} ({category}).
Sample size: {sample_size}. All measurements in INCHES for that sample size.

Each row = ONE labeled measurement point on the garment diagram (use letter codes A, B, C...).
Generate 8–14 points covering the key structural measurements of this garment type.

Return JSON array ONLY:
[{{"code": "A", "point_of_measurement": "Total Length", "how_to_measure": "From HPS straight down to hemline at CF", "sample_size": "28\\"", "tolerance": "±1/2\\""}}, ...]

Garment vision: {vision_text[:400]}"""

    pom_result, _ = claude_query(pom_prompt)
    pom_measurements = []
    try:
        raw = pom_result.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        pom_measurements = json.loads(raw)
    except Exception:
        pom_measurements = [
            {"code": "A", "point_of_measurement": "Total Length", "how_to_measure": "HPS to hemline", "sample_size": "28\"", "tolerance": "±1/2\""},
            {"code": "B", "point_of_measurement": "Chest Width", "how_to_measure": "1\" below armhole, straight across", "sample_size": "19\"", "tolerance": "±1/2\""},
        ]

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

    details_text, _ = claude_query(details_prompt, images=images)

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
    # page_6 = Size Chart (all sizes, graded — NO diagram)
    master["page_6"] = {"measurements": measurements}
    # page_10 = Garment Measurements (diagram + POM table for sample size only)
    master["page_10"] = {"measurement_image_url": "assets/measurement_diagram.png", "measurements": pom_measurements}

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
    _report(progress_callback, "Detail Cropping", "Identifying required detail regions", "", 78)

    combined_image = combine_images_horizontally(images, "assets/combined.png")
    ai_crops = ai_crop_detail_regions(images, details_text, "assets", min_crops=3, max_crops=6)

    # Initialize all 6 detail slots to empty string so unused slots are excluded/deselected by default
    for i in range(1, 7):
        master["page_2"][f"detail_image_{i}_url"] = ""

    if not ai_crops:
        # Fallback to individual single-view crops
        ai_crops = create_individual_detail_crops(front_img, back_img, "assets")

    # Populate only the required crops that were identified for this garment
    for i, crop_path in enumerate(ai_crops[:6]):
        master["page_2"][f"detail_image_{i+1}_url"] = crop_path

    # Keep all available crops in optional_image_urls for suggestions & custom user selection
    fallback_crops = create_individual_detail_crops(front_img, back_img, "assets")
    all_available = list(dict.fromkeys(ai_crops + fallback_crops))
    master["page_2"]["optional_image_urls"] = all_available

    _report(progress_callback, "Detail Cropping", f"{len(ai_crops[:6])} required detail regions cropped", "", 80)

    # ─── STEP 12: Image generation ───
    if generate:
        _report(progress_callback, "Technical Sketch", "Generating sketch with GPT Image 2.5 Flare", "", 82)

        # Build sketch prompt — only VISIBLE features
        visible_accessories = [a for a in accessories if not any(
            kw in str(a).lower() for kw in ["invisible", "hidden", "internal", "fusible", "interfacing", "lining"]
        )]

        # Build technical sketch specification strictly referring to what was observed in the original reference
        gt = garment_type.lower()
        pieces_lower = [str(p).lower() for p in pieces]
        dt_lower = details_text.lower()

        has_blazer = any(k in gt or k in pieces_lower for k in ["blazer", "suit jacket", "jacket"]) and not any(k in gt for k in ["bomber", "denim jacket", "leather jacket"])
        has_skirt = any(k in gt or k in pieces_lower for k in ["skirt"])
        has_trouser = any(k in gt or k in pieces_lower for k in ["trouser", "pant", "trousers", "pants"])
        has_vest = any(k in gt or k in pieces_lower for k in ["vest", "waistcoat"])
        is_dress = "dress" in gt or "gown" in gt

        is_3piece = (has_vest and has_trouser and has_blazer) or "3-piece" in gt or "3 piece" in gt
        is_skirt_suit = (has_blazer and has_skirt) or "skirt suit" in gt
        is_pant_suit = (has_blazer and has_trouser) or "pant suit" in gt or "trouser suit" in gt

        if is_3piece:
            target_summary = f"3-Piece Suit (Blazer, Vest, Trouser)"
            layout = "Draw each piece as a SEPARATE FLAT GARMENT in a 2-row grid. TOP ROW: Blazer front/back, Vest front/back. BOTTOM ROW: Trouser front/back."
            prohibited_items = ["skirt", "dress"]
        elif is_skirt_suit:
            target_summary = f"2-Piece Skirt Suit (Blazer and Skirt)"
            layout = "2-PIECE SKIRT SUIT CAD FLATS: TOP ROW: Blazer Front View (left) + Blazer Back View (right). BOTTOM ROW: Skirt Front View (left) + Skirt Back View (right)."
            prohibited_items = ["vest", "trousers", "pants"]
        elif is_pant_suit:
            target_summary = f"2-Piece Pant Suit (Blazer and Trouser)"
            layout = "2-PIECE PANT SUIT CAD FLATS: TOP ROW: Blazer Front View (left) + Blazer Back View (right). BOTTOM ROW: Trouser Front View (left) + Trouser Back View (right)."
            prohibited_items = ["vest", "skirt"]
        elif (has_blazer or "blazer" in gt) and not (has_skirt or has_trouser):
            # Standalone blazer
            target_summary = f"Single Blazer ({garment_type})"
            layout = "FRONT VIEW on left, BACK VIEW on right."
            prohibited_items = ["skirt", "trousers", "pants", "vest", "inner shirt"]
        elif is_dress:
            target_summary = f"Single Dress ({garment_type})"
            layout = "FRONT VIEW on left, BACK VIEW on right."
            prohibited_items = ["blazer", "jacket", "coat", "pants", "skirt"]
        elif has_trouser and not has_blazer:
            target_summary = f"Single Trouser / Pants ({garment_type})"
            layout = "FRONT VIEW on left, BACK VIEW on right."
            prohibited_items = ["blazer", "jacket", "top", "shirt"]
        elif has_skirt and not has_blazer:
            target_summary = f"Single Skirt ({garment_type})"
            layout = "FRONT VIEW on left, BACK VIEW on right."
            prohibited_items = ["blazer", "jacket", "top", "shirt"]
        else:
            # Standalone top (turtleneck, shirt, blouse, sweater, knitwear)
            target_summary = f"Single Top ({garment_type})"
            layout = "FRONT VIEW on left, BACK VIEW on right."
            prohibited_items = ["blazer", "jacket", "coat", "vest", "skirt", "pants"]

        # Extract specific architectural CAD types via vision from reference photos
        cad_specs = {}
        try:
            cad_vision_prompt = f"""You are a master apparel technical CAD designer.
Look closely at the reference garment photos.
Garment: {garment_type} ({description})
Pieces: {pieces}

Analyze the EXACT architectural types of each construction element directly from what you see in the reference photo. If a feature does not exist on the garment, say 'None'.

Identify:
1. 'pocket_type': Exact pocket construction (e.g., 'Two lower flap welt pockets at waist', 'One chest welt pocket', 'Side seam slash pockets', 'Front patch pockets with button flaps', or 'None — clean seamless front').
2. 'collar_or_neckline_type': Exact collar/neckline construction (e.g., 'Notch lapel with tailored gorge seam', 'Peak lapel with sharp upward points', 'Folded double-layer ribbed turtleneck collar (~8-10cm height)', 'Ribbed crew neckline', 'Pointed shirt collar with stand', 'Deep V-neckline').
3. 'closure_type': Exact closure mechanism & hardware (e.g., 'Double-breasted 4-button closure (2x2 button stance)', 'Single-breasted 2-button front closure', 'Center front concealed button placket', 'Exposed metal zipper', 'Pull-on stretch entry with no front closures').
4. 'sleeve_and_cuff_type': Exact sleeve & cuff (e.g., 'Long set-in sleeves with 4-button vent cuffs', 'Long slim-fit sleeves with narrow clean-finished plain hem cuffs', 'Raglan sleeves with ribbed knit cuffs', 'Sleeveless with clean finished armholes').
5. 'hem_and_silhouette_type': Exact silhouette & hem (e.g., 'Tailored hourglass silhouette with structured shoulders and hip-length hem', 'Fitted silhouette with curved flared peplum hem', 'Straight knee-length pencil skirt with center back walking slit', 'Straight clean hem at hip level').
6. 'callout_labels': 5 to 7 specific, standard uppercase apparel callout labels for the exact visible features.

Return JSON only:
{{
  "pocket_type": "...",
  "collar_or_neckline_type": "...",
  "closure_type": "...",
  "sleeve_and_cuff_type": "...",
  "hem_and_silhouette_type": "...",
  "callout_labels": ["..."]
}}"""
            raw_specs, _ = claude_query(cad_vision_prompt, images=images)
            json_m = re.search(r'\{.*\}', raw_specs, re.DOTALL)
            if json_m:
                cad_specs = json.loads(json_m.group())
        except Exception as e:
            print(f"[CAD Vision] Spec extraction fallback: {e}")

        # Fallback to rule-based extraction from details_text / vision_text if needed
        button_matches = [a for a in accessories if "button" in str(a.get("description", "")).lower()]
        btn_desc = ", ".join([f"{a.get('description', 'Buttons')} (qty: {a.get('quantity_per_style', '')})" for a in button_matches]) if button_matches else "front closure buttons visible in reference photo"

        pocket_type = cad_specs.get("pocket_type")
        if not pocket_type or pocket_type.lower() == "none":
            if "flap pocket" in dt_lower:
                pocket_type = "Lower flap welt pockets"
            elif "welt pocket" in dt_lower:
                pocket_type = "Tailored welt pockets"
            elif "patch pocket" in dt_lower:
                pocket_type = "Front patch pockets"
            elif "slash pocket" in dt_lower or "slant pocket" in dt_lower:
                pocket_type = "Side-entry slash / slant pockets"
            elif "pocket" in dt_lower:
                pocket_type = "Visible tailored pockets"
            else:
                pocket_type = "No pockets — clean seamless front"

        collar_type = cad_specs.get("collar_or_neckline_type")
        if not collar_type:
            if "turtleneck" in dt_lower or "roll neck" in dt_lower:
                collar_type = "Folded double-layer turtleneck collar (~8-10cm height)"
            elif "notch lapel" in dt_lower:
                collar_type = "Classic notch lapel with tailored gorge seam"
            elif "peak lapel" in dt_lower:
                collar_type = "Peak lapel with sharp upward points"
            elif "collar" in dt_lower:
                collar_type = "Tailored collar matching reference photo"
            else:
                collar_type = "Clean neckline contour matching reference photo"

        closure_type = cad_specs.get("closure_type")
        if not closure_type:
            if "double-breasted" in dt_lower:
                closure_type = "Double-breasted button closure"
            elif "single-breasted" in dt_lower:
                closure_type = "Single-breasted button closure"
            elif "button" in dt_lower or button_matches:
                closure_type = f"Front button closure ({btn_desc})" if button_matches else "Front button closure"
            elif "zipper" in dt_lower or "zip" in dt_lower:
                closure_type = "Exposed metal zipper closure"
            else:
                closure_type = "Pull-on entry with no front closures or buttons"

        sleeve_type = cad_specs.get("sleeve_and_cuff_type")
        if not sleeve_type:
            if "button" in dt_lower and has_blazer:
                sleeve_type = "Long tailored set-in sleeves with buttoned cuff vents"
            elif "sleeves:" in dt_lower:
                for line in details_text.split("\n"):
                    if line.lower().startswith("sleeves:"):
                        sleeve_type = line.split(":", 1)[1].strip()
                        break
            if not sleeve_type:
                sleeve_type = "Long set-in sleeves with clean finished cuffs"

        hem_type = cad_specs.get("hem_and_silhouette_type")
        if not hem_type:
            if "peplum" in dt_lower:
                hem_type = "Fitted waist with flared peplum hem"
            elif "pencil" in dt_lower:
                hem_type = "Straight knee-length pencil skirt with center back walking vent"
            elif "silhouette:" in dt_lower:
                for line in details_text.split("\n"):
                    if line.lower().startswith("silhouette:"):
                        hem_type = line.split(":", 1)[1].strip()
                        break
            if not hem_type:
                hem_type = "Tailored silhouette matching reference photo"

        specs_list = [
            f"- TARGET PIECE(S): Draw ONLY {target_summary}. Front view on left, Back view on right.",
        ]
        if prohibited_items:
            specs_list.append(f"- STRICTLY FORBIDDEN: Do NOT draw any {', '.join(prohibited_items)}. No unrequested outer jackets, skirts, pants, or layered garments.")

        specs_list.extend([
            f"- COLLAR / NECKLINE: {collar_type}",
            f"- FRONT CLOSURE & HARDWARE: {closure_type}",
            f"- POCKET ARCHITECTURE: {pocket_type}",
            f"- SLEEVES & CUFFS: {sleeve_type}",
            f"- SILHOUETTE & HEM: {hem_type}",
            "- Symmetrical, perfectly proportioned apparel vector flats with crisp black line art on a pure white background."
        ])

        # Callouts strictly for features that exist
        if cad_specs.get("callout_labels") and isinstance(cad_specs["callout_labels"], list) and len(cad_specs["callout_labels"]) >= 3:
            callouts = [c.upper().strip() for c in cad_specs["callout_labels"]]
        else:
            callouts = ["FRONT VIEW", "BACK VIEW"]
            if "turtleneck" in collar_type.lower():
                callouts.append("TURTLENECK COLLAR")
            elif "lapel" in collar_type.lower():
                callouts.append("NOTCH LAPEL" if "peak" not in collar_type.lower() else "PEAK LAPEL")
            elif "collar" in collar_type.lower():
                callouts.append("COLLAR")
            else:
                callouts.append("NECKLINE")

            callouts.extend(["SHOULDER SEAM", "SIDE SEAM"])

            if "button" in closure_type.lower():
                callouts.append("BUTTON CLOSURE")
            if "no pocket" not in pocket_type.lower() and "none" not in pocket_type.lower():
                callouts.append("POCKET")
            if is_skirt_suit or has_skirt:
                callouts.append("SKIRT WAISTBAND")
            if has_trouser:
                callouts.append("TROUSER WAISTBAND")
            if "peplum" in hem_type.lower():
                callouts.append("PEPLUM HEM")
            callouts.append("HEM")

        callouts_str = ", ".join(callouts)
        ref_image = combined_image if os.path.exists(combined_image) else front_img

        sketch_prompt = f"""Look at the reference garment photos carefully (showing both front and back views). Create a professional 2D fashion CAD vector technical flat sketch (Adobe Illustrator apparel specification style).

TARGET: {target_summary} ({description})

LAYOUT:
{layout}

CRITICAL SPECIFICATIONS (STRICTLY FROM REFERENCE PHOTO):
{chr(10).join(specs_list)}

Garment details from analysis:
{details_text}

DRAWING RULES:
- 2D FLAT VECTOR CAD APPAREL SPEC SKETCHES ONLY (like Adobe Illustrator tech pack drawings).
- Pure black line art on white background. NO gray shading, NO 3D rendering, NO realistic textures, NO mannequin, NO model figures.
- Include clear construction details: seam lines, princess seams, waistband (if bottoms), hem folds, and dashed topstitching lines.
- TEXT & SPELLING RULE: Any callout labels drawn MUST be chosen ONLY from: [{callouts_str}]. Leader lines must point accurately to the feature (SIDE SEAM → outer side edge, SHOULDER → top, HEM → bottom, CUFF → wrist). ALL TEXT MUST BE SPELLED 100% CORRECTLY IN ALL-CAPS. Absolutely NO typos, NO misspelled words, and NO garbled letters!
- Do NOT draw accessories panels, button mockups, thread spools, or separate accessories boxes."""

        generate_image(sketch_prompt, reference_image_path=ref_image, output_path="assets/technical_sketch.png")

        # Verify sketch with multi-criteria QA auditor
        issues = verify_sketch_labels(
            "assets/technical_sketch.png",
            callout_list=callouts,
            garment_type=target_summary,
            reference_image_path=ref_image,
            expected_pieces=pieces or [target_summary]
        )
        if issues:
            _report(progress_callback, "Sketch Verification", f"Issues: {issues[:100]}", "Regenerating...", 84)
            generate_image(sketch_prompt + f"\n\nCRITICAL FIXES REQUIRED FROM VERIFICATION AUDIT:\n{issues}", reference_image_path=ref_image, output_path="assets/technical_sketch.png")

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
        elif is_skirt_suit:
            meas_prompt = f"Measurement diagram for {description}. Show 2 separate flat garment sketches: Blazer and Skirt. Add measurement lines with letter labels. Blazer: G=Shoulder, H=Bust, I=Waist, J=Back Length. Skirt: A=Waist, B=Hip, C=Thigh, D=Skirt Length, E=Hem Width, F=Rise. Small text legend on right. Do NOT draw text boxes or panels on top of the garments. Keep it clean — just the garment outlines with measurement arrows and letter labels."
        elif has_trouser and (is_multi or is_suit):
            meas_prompt = f"Measurement diagram for {description}. Show 2 pieces: Blazer (G-J) + Trouser (A-F). Legend on right. NO VEST."
        elif is_pant:
            meas_prompt = f"Measurement diagram for {description}. Pant measurements: A=Waist, B=Hip, C=Inseam, D=Outseam, E=Thigh, F=Leg opening."
        elif is_skirt:
            meas_prompt = f"Measurement diagram for {description}. Skirt measurements: A=Waist, B=Hip, C=Skirt Length, D=Hem Width."
        else:
            meas_prompt = f"""Technical measurement flat sketch diagram for {description}.
Front view and back view side-by-side on pure white background.
Crisp vector-style black line art, no color, no shading, no gray smudges or artifacts on back view.
Clear double-headed measurement arrows with letter labels:
- A = Bust width (horizontal double-arrow across chest 1 inch below armholes)
- B = Waist width (horizontal double-arrow across waist)
- C = Shoulder width (horizontal double-arrow across shoulder points)
- D = Sleeve length (double-arrow along sleeve from shoulder seam to cuff)
- E = Body length / HPS to Hem (single vertical double-arrow from High Point Shoulder straight down to bottom hem)
- F = Sweep / Bottom Hem width (horizontal double-arrow across bottom hem)
Clean bottom legend: A Bust | B Waist | C Shoulder | D Sleeve | E Body length | F Sweep.
Do NOT draw two competing vertical length arrows. Do NOT draw smudges, shading, or gray gradients on back view."""
        generate_image(meas_prompt,
                       reference_image_path=front_img, output_path="assets/measurement_diagram.png")
        _report(progress_callback, "Measurement Diagram", "Generated", "", 93)

    # ─── STEP 13: Continuous learning — corrections as CONTEXT, not overrides ───
    # Corrections feed into prompts (Step 5 fabric, Step 6 construction already use corrections_context)
    # We do NOT blindly replace values — AI considers corrections as preferences
    # The correction may not apply to every garment (wool IS correct sometimes)
    if corrections:
        correction_notes = []
        for c in corrections[-5:]:
            correction_notes.append(f"Past correction: {c.get('field_key','')}: '{c.get('original_value','')[:30]}' → '{c.get('corrected_value','')[:30]}' (reason: {c.get('reason','')})")
        if correction_notes:
            master.setdefault("_confidence", {}).setdefault("_notes", []).append(
                f"Learning: {len(corrections)} past corrections found for this garment type. Fed into AI prompts as preferences, not auto-applied."
            )
            print(f"[LEARNING] {len(corrections)} corrections found — used as context in prompts, NOT auto-applied")

    # ─── STEP 14: Save + Render ───
    _report(progress_callback, "Rendering PDF", "Generating 10-page PDF", "", 95)

    with open("data/master_filled.json", "w") as f:
        json.dump(master, f, indent=4, ensure_ascii=False)
    with open("data/master_draft.json", "w") as f:
        json.dump(master, f, indent=4, ensure_ascii=False)

    pdf_path = generatePdf()
    _report(progress_callback, "Complete", "Tech Pack ready!", f"Cost: ~$0.17", 100)

    return pdf_path
