#!/usr/bin/env python3
"""
Image generation helper for the /techpack skill.
Generates: technical sketch, brand label, care label.
All via OpenRouter (supports GPT Image 2.5 Flare + Gemini models).

Usage:
  python skill_image_gen.py \
    --front assets/front.png \
    --back assets/back.png \
    --description "Men's Double-Breasted Trench Coat" \
    --brand "PRIVY" \
    --collection "JC PRIVATE" \
    --callouts "WIDE COLLAR,BELT,DOUBLE BREASTED,FLAP POCKETS,EPAULETTES" \
    --composition "100% Cotton Gabardine" \
    --care "Machine wash cold. Do not bleach. Tumble dry low."
"""

import os
import re
import sys
import json
import base64
import argparse
import requests
import time
from pathlib import Path
from io import BytesIO
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path)

ASSETS_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "assets"

# Model priority: GPT Image 2.5 Flare (best text/labels) → Gemini Pro → Gemini Flash
IMAGE_MODELS = [
    "openai/gpt-image-2.5-flare",
    "google/gemini-3-pro-image",
    "google/gemini-3.1-flash-image-preview",
]

# Vision model for verification (cheap, fast)
VERIFY_MODEL = os.getenv("VERIFY_MODEL", "google/gemini-2.5-flash")


def verify_sketch_labels(sketch_path: str, callout_list: list) -> str:
    """Use vision LLM to check if sketch labels point to correct garment locations.
    Returns empty string if OK, or description of issues if wrong."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or not os.path.exists(sketch_path):
        return ""  # skip verification if no key or no image

    try:
        data_url = _image_to_base64_url(sketch_path)
        callouts_str = ", ".join(callout_list)

        prompt = f"""Look at this technical garment sketch. It has callout labels with leader lines pointing to garment features.

Check if each label's leader line points to the CORRECT location on the garment:
- SIDE SEAM should point to the SIDE EDGE of the garment (not center)
- SHOULDER SEAM should point to the TOP of the shoulder
- ARMHOLE SEAM should point to where sleeve meets body
- CENTER BACK SEAM should point to the center line of the back view
- HEM should point to the bottom edge
- COLLAR/NECKLINE should point to the neck area
- CUFF should point to the wrist/end of sleeve

Expected labels: {callouts_str}

If ALL labels point to the correct locations, respond with exactly: OK
If any label points to the WRONG location, respond with a brief description of what's wrong.
Example: "SIDE SEAM label points to center front instead of the side edge"

Respond with ONLY "OK" or the issue description. Nothing else."""

        payload = {
            "model": VERIFY_MODEL,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": prompt}
            ]}],
            "max_tokens": 200,
            "temperature": 0,
        }

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=30,
        )

        if response.status_code != 200:
            return ""  # skip on error

        msg = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        if isinstance(msg, list):
            msg = " ".join(p.get("text", "") for p in msg if isinstance(p, dict))

        msg = msg.strip()
        if msg.upper() == "OK" or not msg:
            return ""
        return msg

    except Exception as e:
        print(f"  Verification error: {e}")
        return ""  # skip on error


def _image_to_base64_url(path: str) -> str:
    ext = path.lower().rsplit(".", 1)[-1]
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "image/png")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _save_image_from_b64(b64_data: str, output_path: str) -> str:
    from PIL import Image
    img_bytes = base64.b64decode(b64_data)
    img = Image.open(BytesIO(img_bytes))
    img.save(output_path)
    print(f"  ✓ Saved: {output_path}")
    return output_path


def generate_image_openrouter(prompt: str, output_path: str = "output.png", model: str = None, reference_image_path: str = None) -> str:
    """Generate image via OpenRouter /images endpoint. Supports optional reference image via input_references."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in .env")

    if model is None:
        model = IMAGE_MODELS[0]

    payload = {"model": model, "prompt": prompt, "n": 1}

    # Add reference image for image-to-image generation
    if reference_image_path and os.path.exists(reference_image_path):
        data_url = _image_to_base64_url(reference_image_path)
        payload["input_references"] = [
            {"type": "image_url", "image_url": {"url": data_url}}
        ]

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/images",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload, timeout=240,
            )
            if response.status_code == 429:
                print(f"  Rate limited. Waiting 35s... (attempt {attempt+1}/{max_retries})")
                time.sleep(35)
                continue
            if response.status_code != 200:
                raise RuntimeError(f"API error {response.status_code}: {response.text[:300]}")

            images = response.json().get("data", [])
            if images:
                b64 = images[0].get("b64_json", "")
                if b64:
                    return _save_image_from_b64(b64, output_path)
                url = images[0].get("url", "")
                if url:
                    img_resp = requests.get(url, timeout=60)
                    with open(output_path, "wb") as f:
                        f.write(img_resp.content)
                    print(f"  ✓ Saved: {output_path}")
                    return output_path
            raise RuntimeError(f"No image in response from {model}")
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                continue
            raise
    raise RuntimeError(f"Failed after {max_retries} attempts")


def generate_image_with_reference(prompt: str, reference_image_path: str, output_path: str = "output.png", model: str = "google/gemini-3-pro-image") -> str:
    """Generate image via OpenRouter /chat/completions with a reference image input.
    Uses Gemini models which support image-in + image-out."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in .env")

    content = []
    if reference_image_path and os.path.exists(reference_image_path):
        data_url = _image_to_base64_url(reference_image_path)
        content.append({"type": "image_url", "image_url": {"url": data_url}})
    content.append({"type": "text", "text": prompt})

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 4096,
        "temperature": 0.3,
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload, timeout=180,
            )
            if response.status_code == 429:
                print(f"  Rate limited. Waiting 35s... (attempt {attempt+1}/{max_retries})")
                time.sleep(35)
                continue
            if response.status_code != 200:
                raise RuntimeError(f"API error {response.status_code}: {response.text[:300]}")

            res_data = response.json()
            msg = res_data.get("choices", [{}])[0].get("message", {})
            msg_content = msg.get("content", "")

            # Parse response — could be string or list of content blocks
            if isinstance(msg_content, list):
                for part in msg_content:
                    if isinstance(part, dict):
                        if part.get("type") == "image_url":
                            url = part.get("image_url", {}).get("url", "")
                            if url.startswith("data:"):
                                b64_data = url.split(",", 1)[1]
                                return _save_image_from_b64(b64_data, output_path)
                            elif url.startswith("http"):
                                img_resp = requests.get(url, timeout=60)
                                with open(output_path, "wb") as f:
                                    f.write(img_resp.content)
                                print(f"  ✓ Saved: {output_path}")
                                return output_path
                        elif part.get("type") == "text":
                            text = part.get("text", "")
                            match = re.search(r'data:image/\w+;base64,([A-Za-z0-9+/=]+)', text)
                            if match:
                                return _save_image_from_b64(match.group(1), output_path)

            elif isinstance(msg_content, str):
                match = re.search(r'data:image/\w+;base64,([A-Za-z0-9+/=]+)', msg_content)
                if match:
                    return _save_image_from_b64(match.group(1), output_path)

            raise RuntimeError(f"No image found in response from {model}")
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                continue
            raise
    raise RuntimeError(f"Failed after {max_retries} attempts")


def generate_image(prompt: str, reference_image_path: str = None, output_path: str = "output.png") -> str:
    """Generate image via OpenRouter /images. Uses input_references when reference image provided."""
    errors = []
    for model in IMAGE_MODELS:
        try:
            print(f"  Trying {model}{'  (with reference)' if reference_image_path else ''}...")
            return generate_image_openrouter(prompt, output_path, model=model, reference_image_path=reference_image_path)
        except Exception as e:
            print(f"  Failed with {model}: {str(e)[:150]}")
            errors.append(f"{model}: {e}")
    raise RuntimeError(f"All image models failed:\n" + "\n".join(errors))


def main():
    parser = argparse.ArgumentParser(description="Generate tech pack images")
    parser.add_argument("--front", required=True, help="Front garment image path")
    parser.add_argument("--back", required=True, help="Back garment image path")
    parser.add_argument("--description", required=True, help="Garment description")
    parser.add_argument("--brand", required=True, help="Brand name")
    parser.add_argument("--collection", default="JC PRIVATE", help="Collection name")
    parser.add_argument("--callouts", required=True, help="Comma-separated callout labels")
    parser.add_argument("--composition", required=True, help="Fabric composition")
    parser.add_argument("--care", required=True, help="Care instructions summary")
    parser.add_argument("--do-not-draw", default="", help="Comma-separated features to explicitly exclude from sketch")
    args = parser.parse_args()

    ASSETS_DIR.mkdir(exist_ok=True)
    callout_list = [c.strip() for c in args.callouts.split(",")]
    callout_text = "\n".join(f"- {c}" for c in callout_list)

    # Build DO NOT DRAW list
    do_not_draw_items = [item.strip() for item in args.do_not_draw.split(",") if item.strip()] if args.do_not_draw else []
    do_not_draw_text = ""
    if do_not_draw_items:
        do_not_draw_text = "\n\nCRITICAL — DO NOT DRAW any of these (they do NOT exist on this garment):\n"
        do_not_draw_text += "\n".join(f"- {item}" for item in do_not_draw_items)

    # --- 1. Technical Sketch ---
    print("\n[1/4] Generating Technical Sketch...")
    sketch_prompt = f"""Create a professional technical flat sketch (fashion CAD line drawing) of a {args.description}.

LAYOUT: Two views side by side — FRONT VIEW on the left, BACK VIEW on the right.

DRAW EXACTLY THESE FEATURES with callout label lines (and NOTHING else):
{callout_text}

LABEL PLACEMENT RULES (VERY IMPORTANT — labels must point to the CORRECT location):
- SIDE SEAM: leader line must point to the OUTER EDGE of the garment body (left or right side), NOT the center
- SHOULDER SEAM: leader line must point to the TOP of the shoulder where sleeve meets body
- ARMHOLE SEAM: leader line must point to where the sleeve attaches to the body (armpit area)
- CENTER BACK SEAM: leader line must point to the CENTER LINE of the back view
- HEM: leader line must point to the BOTTOM EDGE of the garment
- COLLAR/NECKLINE: leader line must point to the TOP/NECK area
- CUFF: leader line must point to the END of the sleeve (wrist area)
- POCKET: leader line must point to the HIP/WAIST area where pocket is located
- Labels on the LEFT side of the sketch should have leader lines going LEFT → garment
- Labels on the RIGHT side should have leader lines going RIGHT → garment

DRAWING RULES:
- Draw ONLY the features listed above. If a feature is not listed, it does not exist on this garment.
- Match the exact silhouette and proportions from the reference image.
- Every callout must have a thin leader line from the label text to the EXACT correct location on the garment.
- All label text must be ALL-CAPS and clearly readable.
- Label "FRONT VIEW" above the left drawing and "BACK VIEW" above the right drawing.
{do_not_draw_text}
STYLE:
- Pure black line art on white background
- No shading, no gradients, no color fill
- Clean professional fashion technical flat drawing
- Consistent line weight throughout"""

    sketch_path = str(ASSETS_DIR / "technical_sketch.png")
    generate_image(
        sketch_prompt,
        reference_image_path=args.front,
        output_path=sketch_path
    )

    # --- 1B. Verify sketch label placement ---
    print("  Verifying label placement...")
    verification_issues = verify_sketch_labels(sketch_path, callout_list)
    if verification_issues:
        print(f"  ⚠️ Label issues found: {verification_issues}")
        print("  Regenerating with corrections...")
        correction_prompt = sketch_prompt + f"\n\nCORRECTION NEEDED: {verification_issues}\nFix the label placement so each leader line points to the correct garment location."
        generate_image(
            correction_prompt,
            reference_image_path=args.front,
            output_path=sketch_path
        )
        print("  ✓ Regenerated with corrections")
    else:
        print("  ✓ Labels verified OK")

    # --- 2. Brand Label ---
    print("\n[2/4] Generating Brand Label...")
    brand_prompt = f"""Create a clean, professional woven garment brand label mockup.

The label should show:
- Brand name "{args.brand}" in bold serif font at the top
- Below: "{args.description}" in smaller text
- Below: "https://{args.brand.lower().replace(' ', '')}brand.com/" in small text

Style:
- White background with black text
- Subtle shadow/card effect
- Clean, minimal design like a real woven label
- Size: roughly 5cm wide × 3cm tall proportions
- No decorative borders or patterns"""

    generate_image(
        brand_prompt,
        output_path=str(ASSETS_DIR / "brand_label_final.png")
    )

    # --- 3. Care Label ---
    print("\n[3/4] Generating Care Label...")
    care_prompt = f"""Create a realistic folded fabric care label for a garment.

The label must show:
TOP SECTION:
- "{args.composition}" in bold text

MIDDLE SECTION (care symbols row):
- Standard ISO 3758 laundry care symbols in a row (wash tub, triangle, square, iron, circle)

TEXT SECTION:
- {args.care}

BOTTOM:
- "MADE IN INDIA" in a bordered box

Style:
- White/off-white fabric texture background
- Black text
- Looks like an actual printed/woven garment care label
- Slightly folded for realism
- Approximately 5cm wide × 8cm tall proportions"""

    generate_image(
        care_prompt,
        output_path=str(ASSETS_DIR / "care_label_final.png")
    )

    # --- 4. Measurement Diagram ---
    print("\n[4/4] Generating Measurement Diagram...")

    # Detect garment type for measurement-specific labels
    desc_lower = args.description.lower()
    if any(w in desc_lower for w in ["3-piece", "3 piece", "suit"]) and any(w in desc_lower for w in ["pant", "trouser", "vest"]):
        measurement_points = """Show ALL 3 pieces as SEPARATE flat garments in a grid:
TOP ROW (smaller, with blazer measurement lines): Blazer front/back, Vest front/back
BOTTOM ROW (larger, with trouser measurement lines): Trouser front/back

BLAZER measurements:
- G = Chest/Bust width (horizontal across chest)
- H = Shoulder width (horizontal across shoulders)
- I = Sleeve length (vertical shoulder to cuff)
- J = Blazer length (vertical shoulder to hem)

TROUSER measurements:
- A = Waist width (horizontal at waistband)
- B = Hip width (horizontal at hip)
- C = Inseam (vertical inner leg)
- D = Outseam (vertical outer leg)
- E = Thigh width (horizontal at upper thigh)
- F = Leg opening (horizontal at hem)

Include a MEASUREMENT LEGEND on the right side listing A through J."""
    elif any(w in desc_lower for w in ["pant", "trouser", "jean", "short"]):
        measurement_points = """- A = Waist width (horizontal double-arrow across waistband)
- B = Hip width (horizontal double-arrow at fullest hip point)
- C = Inseam (vertical line from crotch to hem, along inner leg)
- D = Outseam (vertical line from waist to hem, along outer leg)
- E = Thigh width (horizontal double-arrow at upper thigh)
- F = Leg opening (horizontal double-arrow at hem)

IMPORTANT: This is a PANT. Use ONLY pant measurements. Do NOT use chest, bust, shoulder, or sleeve."""
    elif any(w in desc_lower for w in ["skirt"]):
        measurement_points = """- A = Waist width (horizontal double-arrow across waistband)
- B = Hip width (horizontal double-arrow at fullest hip)
- C = Skirt length (vertical line from waist to hem)

IMPORTANT: This is a SKIRT. Use ONLY skirt measurements."""
    elif any(w in desc_lower for w in ["dress", "gown"]):
        measurement_points = """- A = Bust width (horizontal double-arrow across chest)
- B = Waist width (horizontal double-arrow at waist)
- C = Hip width (horizontal double-arrow at hip)
- D = Dress length (vertical line from shoulder to hem)
- E = Sleeve length (if applicable)

IMPORTANT: This is a DRESS. Use dress-specific measurements."""
    else:
        # Default: upper body (coat, jacket, cardigan, shirt, blouse)
        measurement_points = """- A = Chest/Bust width (horizontal double-arrow across chest)
- B = Waist width (horizontal double-arrow at waist)
- C = Shoulder width (horizontal double-arrow across shoulders)
- D = Sleeve length (vertical line from shoulder to cuff)
- E = Total garment length (vertical line from shoulder to hem)
- F = Front length (shoulder to front hem)"""

    measurement_prompt = f"""Based on this garment image, create a clean technical flat sketch measurement diagram for a {args.description}.

Draw FRONT VIEW and BACK VIEW flat sketches (black line art, no color, no shading) with measurement indicator lines:
{measurement_points}

Each measurement line must have its letter label (A, B, C, etc.) clearly visible.
The sketch must match the EXACT silhouette and proportions of the reference garment.
Pure black line art on white background. No color. No shading."""

    generate_image(
        measurement_prompt,
        reference_image_path=args.front,
        output_path=str(ASSETS_DIR / "measurement_diagram.png")
    )

    print("\n✅ All images generated successfully!")
    print(f"  - Technical sketch: assets/technical_sketch.png")
    print(f"  - Brand label: assets/brand_label_final.png")
    print(f"  - Care label: assets/care_label_final.png")
    print(f"  - Measurement diagram: assets/measurement_diagram.png")


if __name__ == "__main__":
    main()
