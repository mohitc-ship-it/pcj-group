"""
image_verifier.py

Uses Claude Vision (claude-sonnet) to verify each AI-generated image
against a quality checklist. Auto-regenerates with a corrective prompt if failed.
"""

import os
import json
from llm import analyze_images

QUALITY_CHECKS = {
    "technical_sketch": """You are reviewing a fashion technical sketch for a factory tech pack.

Check ALL of the following:
1. BACKGROUND — Is the background clean white? (FAIL if dark/colored background)
2. LINE STYLE — Are lines black/dark and clean? (FAIL if colored fills, gradients, or photographic elements)
3. GARMENT VISIBLE — Is a garment clearly drawn? (FAIL if it looks like a photograph)
4. NO MODEL — Is the model face/body removed? (FAIL if human face/skin prominently visible)
5. FLAT SKETCH — Does it look like a flat technical drawing?

Respond ONLY in this exact JSON format (no markdown):
{"valid": true, "issues": [], "score": 8, "corrective_hint": ""}

Be strict. Score 7+ = valid.""",

    "brand_label": """You are reviewing a brand label image for a fashion tech pack.

Check:
1. LABEL SHAPE — Does it look like a fabric label (rectangular/tag shape)?
2. TEXT VISIBLE — Is there text visible on the label?
3. CLEAN DESIGN — Is it minimal and clean?
4. NO BACKGROUND CLUTTER — Is the background clean?

Respond ONLY in this exact JSON format (no markdown):
{"valid": true, "issues": [], "score": 8, "corrective_hint": ""}

Score 6+ = valid.""",

    "care_label": """You are reviewing a care/wash label image for a fashion tech pack.

Check:
1. CARE SYMBOLS — Are there recognizable laundry/care icons visible (wash tub, triangle, square, circle)?
2. LABEL FORMAT — Does it look like a compact care label?
3. READABLE — Is it clear enough to read?

Respond ONLY in this exact JSON format (no markdown):
{"valid": true, "issues": [], "score": 8, "corrective_hint": ""}

Score 6+ = valid.""",

    "measurement_diagram": """You are reviewing a measurement diagram for a fashion tech pack.

Check:
1. GARMENT SHAPE — Is a garment outline drawn?
2. DIMENSION LINES — Are measurement lines, arrows, or markers visible?
3. LETTER MARKERS — Are there letter labels (A, B, C, D) or number markers?
4. CLEAN STYLE — Is it a clean technical drawing style?

Respond ONLY in this exact JSON format (no markdown):
{"valid": true, "issues": [], "score": 8, "corrective_hint": ""}

Score 6+ = valid."""
}

CORRECTIVE_PREFIXES = {
    "technical_sketch": (
        "CRITICAL CORRECTION: Generate a pure technical flat sketch. "
        "WHITE background ONLY. BLACK line art ONLY. NO colors, NO fills, NO gradients, NO shading. "
        "NO human face or skin visible. Remove all background elements. Clean factory-ready CAD style. "
    ),
    "brand_label": (
        "CRITICAL CORRECTION: Generate a clean fabric brand label. "
        "Simple rectangular tag shape. White or cream background. Brand name text clearly visible. "
        "Minimal design. No decorative background. No scenes. Just the label itself. "
    ),
    "care_label": (
        "CRITICAL CORRECTION: Generate a standard garment care label. "
        "Must show clear laundry care symbols: wash tub icon, bleach triangle, dry square, iron icon. "
        "Compact label format. Clean white background. Industry standard ISO care symbols. "
    ),
    "measurement_diagram": (
        "CRITICAL CORRECTION: Generate a clean technical measurement diagram. "
        "Show garment outline with RED dimension arrows and letter placeholders (A, B, C, D...). "
        "White background. Black garment outline. Red measurement arrows. No color fills. "
    ),
}

# Appended to ALL corrective prompts — tells the model to only fix listed issues,
# never alter garment structure, stitching, accessories, or silhouette
GARMENT_PRESERVATION_RULE = (
    "IMPORTANT — DO NOT CHANGE: Preserve ALL original garment details exactly as provided. "
    "Do NOT change: stitching type, seam details, accessories (buttons, zippers, trim, pockets), "
    "garment silhouette, collar style, sleeve design, or any other construction feature. "
    "Only fix the specific issues listed above. Everything else must remain identical to the original prompt."
)


def verify_image(image_path: str, image_type: str) -> dict:
    """Verify a generated image using Claude Vision."""
    if not os.path.exists(image_path):
        return {"valid": False, "issues": ["Image file not found"], "score": 0, "corrective_hint": ""}

    checklist = QUALITY_CHECKS.get(image_type)
    if not checklist:
        return {"valid": True, "issues": [], "score": 10, "corrective_hint": ""}

    try:
        raw, _think = analyze_images([image_path], checklist, enable_thinking=True)
        raw = raw.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        result = json.loads(raw)
        return {
            "valid": result.get("valid", False),
            "issues": result.get("issues", []),
            "score": result.get("score", 0),
            "corrective_hint": result.get("corrective_hint", ""),
            "thinking": _think
        }
    except Exception as e:
        print(f"[image_verifier] Verification error for {image_type}: {e}")
        # On error, assume valid so pipeline is not blocked
        return {"valid": True, "issues": [f"Verification error: {str(e)[:80]}"], "score": 7, "corrective_hint": "", "thinking": ""}


def verify_and_regenerate(
    image_path: str,
    image_type: str,
    original_prompt: str,
    generate_fn,
    ref_image: str = None,
    max_retries: int = 2,
) -> tuple:
    """
    Verify a generated image and regenerate if it fails.
    
    Strategy:
    - Attempt 0 (first gen)  → already done, just verify
    - Attempt 1 (first retry) → use Flash model (fast, cheap) with corrective prompt
    - Attempt 2+ (final retry) → escalate to Pro model for best quality

    Args:
        image_path:      path to the generated image
        image_type:      'technical_sketch' | 'brand_label' | 'care_label' | 'measurement_diagram'
        original_prompt: original generation prompt
        generate_fn:     callable(prompt, ref_image, output_path, use_pro=bool) -> output_path
        ref_image:       optional reference image path
        max_retries:     max regeneration attempts

    Returns:
        (final_path: str, log: list of attempt dicts)
    """
    log = []

    for attempt in range(max_retries + 1):
        result = verify_image(image_path, image_type)
        result["attempt"] = attempt + 1
        log.append(result)

        if result["valid"]:
            print(f"[image_verifier] {image_type} ✅ PASSED (score={result['score']}, attempt={attempt + 1})")
            return image_path, log

        print(f"[image_verifier] {image_type} ❌ FAILED (score={result['score']}, attempt={attempt + 1}): {result['issues']}")

        if attempt >= max_retries:
            print(f"[image_verifier] {image_type} — max retries reached, keeping last output")
            break

        # Build corrective prompt: correction prefix + garment preservation + hint + original
        corrective_prefix = CORRECTIVE_PREFIXES.get(image_type, "")
        hint = result.get("corrective_hint", "")
        corrective_prompt = (
            corrective_prefix
            + (hint + " " if hint else "")
            + GARMENT_PRESERVATION_RULE + " "
            + original_prompt
        )

        # Escalate to Pro model on the last retry attempt
        use_pro = (attempt >= max_retries - 1)
        model_label = "Pro" if use_pro else "Flash"
        print(f"[image_verifier] Regenerating {image_type} with {model_label} model (attempt {attempt + 2})...")

        new_path = generate_fn(corrective_prompt, ref_image, image_path, use_pro=use_pro)
        if new_path:
            image_path = new_path

    return image_path, log
