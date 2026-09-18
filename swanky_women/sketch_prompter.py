"""
swanky_women/sketch_prompter.py

Provides two prompt flows for 2D technical flat CAD sketches:
1. Normal text prompt flow (structured technical markdown)
2. JSON prompt flow:
   - Generated directly from garment analysis/specs
   - Converted from a normal prompt into structured JSON
"""

import json
from typing import Dict, Any, List, Optional


def build_normal_sketch_prompt(
    page2_details: Any,
    construction_decisions: Any,
    accessories: List[Any],
    is_two_piece: bool = False,
    garment_type: str = ""
) -> str:
    """Build the standard text/markdown technical sketch prompt with strict rules."""
    if is_two_piece:
        layout_instruction = """CANVAS & LAYOUT:
- Wide landscape canvas (21:9 aspect ratio).
- Create the technical sketch showing 4 parts horizontally: [Top Front] [Top Back] [Bottom Front] [Bottom Back].
- Both upper wear and bottom wear must be clearly depicted front and back without model or human body."""
    else:
        layout_instruction = """CANVAS & LAYOUT:
- Wide landscape canvas (21:9 aspect ratio).
- Create the technical sketch showing exactly TWO views arranged horizontally side-by-side:
  * Left side: [Front View]
  * Right side: [Back View]"""

    return f"""Convert the provided image of a model wearing a garment into a professional fashion technical sketch suitable for a production tech pack.

Output Requirements:
- 2D fashion CAD vector line illustration on pure white body (#ffffff) with thin black technical contour lines.
- Pure white background (#ffffff). NO gray or colored body fills (collar stand or cuffs may have subtle contrast shading ONLY if present in reference).
- Garment only (remove model facial and body features, no mannequin).

{layout_instruction}

Strict Feature & Count Accuracy:
- Accurately reflect the exact count of buttons, pockets, seams, and trims seen in the reference photos and accessories specification.
- Vertical Proportions: Maintain tall, elongated vertical fashion proportions. Do NOT draw garments compressed, short-heighted, or stumpy.
- SLEEVE COMPLETENESS (CRITICAL):
  * Both left and right sleeves MUST be drawn completely with finished cuffs on both Front and Back views.
  * Leave generous canvas margin/padding around both sides so neither sleeve is cropped, truncated, or omitted at canvas edges.
- HEMLINE BALANCE & EQUAL FRONT/BACK LENGTH RULE (CRITICAL DOUBLE-CHECK):
  * For T-shirts, nightdresses, shirts, blouses, tops, and dresses: Check the front and back hem levels very carefully.
  * FRONT and BACK views MUST HAVE EXACTLY EQUAL TOTAL VERTICAL LENGTH from shoulder to bottom hem.
  * The bottom hemline of the back view MUST align horizontally at the exact same vertical baseline level as the front view hemline.
  * DO NOT artificially lengthen the back panel, extend the backside lower, or add an unwanted hi-low / curved scoop drop hem.
- BUTTON COUNT ACCOUNTING & DISAMBIGUATION (COLLAR STAND VS PLACKET):
  * When a shirt/blouse specifies a total count of front buttons (e.g., 6 buttons), this count ALREADY INCLUDES the collar stand button.
  * Exact breakdown: 1 collar stand button + 5 front placket buttons = 6 buttons TOTAL.
  * DO NOT draw 6 placket buttons and then add an extra collar button (which erroneously totals 7).
- Zipper Placement: Check closure location precisely. If the garment has a side invisible zipper, place it at the side seam and leave the center back as a clean vertical seam. Only draw a center back zipper if it genuinely opens at center back.
- Sleeve cuffs: Accurately show buttons on barrel cuffs AND sleeve gauntlet plackets (e.g. 2 cuff + 1 gauntlet = 3 per sleeve).
- Back construction: Clean horizontal back yoke with subtle central knife pleats/tucks only if present on reference. Completely smooth back with NO random extra vertical lines or pleats.

Annotation & Labeling:
- BRAND & SIZE LABEL: In the Front View, inside the inner back neckline/collar opening, always illustrate the small rectangular brand neck tag, labeled with a leader line: 'BRAND & SIZE LABEL'.
- Use clean, thin RED LEADER LINES connecting each uppercase label text directly to its corresponding garment feature.
- CONCISE CALLOUT LABELS: Use standard short 1-4 word fashion tech pack callouts (e.g. 'BRAND & SIZE LABEL', 'COLLAR', 'FRONT PLACKET', 'LONG SLEEVES WITH CUFF', 'BACK YOKE', 'CUFFS PLACKET', 'CENTER BACK SEAM'). Do NOT write long paragraphs or descriptive sentences as labels.
- CRITICAL: Keep ONLY the garment drawings, leader lines, and callout label text in the image.
  DO NOT include any bottom specification bars, SEAMS & TRIMS note boxes, borders, titles, 'FRONT VIEW'/'BACK VIEW' text, or headers in the image.

Don't draw any lines or zippers or buttons or any other details, until specified in accessories.

Garment Details to Label:
{page2_details}

Seams & Construction:
{construction_decisions}

Accessories / Trims / Hardware:
{accessories}

Style Guidance:
- Technical flat illustration (fashion CAD)
- Precise proportions and symmetry
- Minimalist, professional, factory-ready

Do not invent details. Only label what is explicitly provided.
"""


def build_json_sketch_prompt(
    page2_details: Any,
    construction_decisions: Any,
    accessories: List[Any],
    is_two_piece: bool = False,
    garment_type: str = "",
    brand_collection: str = ""
) -> str:
    """Build a structured JSON prompt directly from garment specs and technical rules."""
    
    # Format callouts from accessories and page2_details
    callouts = []
    callouts.append({
        "label": "BRAND & SIZE LABEL",
        "target": "Inner back neckline / collar opening on Front View"
    })
    
    if isinstance(accessories, list):
        for acc in accessories:
            if isinstance(acc, dict):
                name = acc.get("name") or acc.get("item") or acc.get("type", "")
                placement = acc.get("placement") or acc.get("location", "")
                if name and name.upper() not in [c["label"] for c in callouts]:
                    callouts.append({
                        "label": name.upper(),
                        "target": placement or f"{name} on garment"
                    })

    json_payload = {
        "task": "2D Fashion CAD Technical Flat Sketch",
        "target_output": "Production Factory Tech Pack Flat Sketch",
        "canvas": {
            "background_color": "#ffffff",
            "aspect_ratio": "21:9",
            "framing": "Wide landscape canvas showing full garments side-by-side horizontally isolated on pure white"
        },
        "style": {
            "type": "2D vector CAD line art",
            "garment_body_color": "Pure white (#ffffff) fabric body with thin clean black technical contour lines",
            "rendering": "Minimalist CAD line illustration, NO dark body fills, NO textures, NO shading",
            "human_elements": "Strictly NONE (no face, no body, no mannequin, no limbs)"
        },
        "proportions_and_silhouette": {
            "proportions": "Tall, elongated vertical fashion proportions (height-to-width >= 2.5:1)",
            "silhouette": "True to reference garment fit and shape (no boxy or stumpy compression)",
            "symmetry": "Precise industrial garment symmetry",
            "sleeve_completeness": "Both left and right sleeves MUST be drawn completely with finished cuffs on both Front and Back views. Neither sleeve may be cut off, omitted, or cropped."
        },
        "hemline_balance": {
            "rule": "EQUAL_FRONT_AND_BACK_LENGTH",
            "strict_constraint": (
                "For T-shirts, shirts, nightdresses, tops, and dresses: FRONT and BACK views MUST have EXACTLY EQUAL total vertical length from shoulder to bottom hem. "
                "The bottom hem of the back view MUST align horizontally at the exact same vertical baseline level as the front view hem. "
                "Strictly DO NOT extend the backside length or add an artificial hi-low drop hem unless explicitly present in reference."
            )
        },
        "button_accounting": {
            "rule": "TOTAL BUTTON COUNT INCLUDES COLLAR STAND BUTTON",
            "clarification": "If the garment has 6 front buttons total, the breakdown is: 1 collar stand button + 5 front placket buttons = 6 buttons total. DO NOT draw 6 placket buttons and then add an extra collar button."
        },
        "layout": {
            "arrangement": "4 parts horizontally: [Top Front] [Top Back] [Bottom Front] [Bottom Back]" if is_two_piece else "2 views side-by-side: Front View on left, Back View on right",
            "view_count": 4 if is_two_piece else 2,
            "canvas_padding": "Generous horizontal margins ensuring full visibility of both sleeves and cuffs on both views without edge clipping."
        },
        "construction_and_seams": construction_decisions if isinstance(construction_decisions, (dict, list)) else str(construction_decisions),
        "accessories_and_trims": accessories if isinstance(accessories, (dict, list)) else str(accessories),
        "annotations": {
            "leader_lines": "Thin red leader lines (#e74c3c)",
            "typography": "Uppercase sans-serif concise technical callouts (1-4 words each)",
            "callouts": callouts[:8]
        },
        "negative_constraints": [
            "NO truncated, cut off, or missing sleeves/cuffs (both sleeves must be drawn in full on both views)",
            "NO extra buttons beyond total count (do not add an extra collar button over the placket count)",
            "NO extended backside hem (front and back lengths must be equal)",
            "NO artificial hi-low or dropped back hem",
            "NO human face, skin, hands, or model features",
            "NO dark, gray, or patterned background (pure white #ffffff only)",
            "NO bottom specification bars, note tables, or border boxes",
            "NO [FRONT VIEW] or [BACK VIEW] text titles"
        ]
    }
    
    return json.dumps(json_payload, indent=2)


def convert_text_to_json_prompt(text_prompt: str) -> str:
    """Converts a standard text prompt into structured JSON format."""
    payload = {
        "task": "2D Fashion CAD Technical Flat Sketch",
        "instructions": "Follow the structured technical tech pack flat sketch rules",
        "canvas": {
            "background": "#ffffff",
            "aspect_ratio": "21:9"
        },
        "hemline_rule": {
            "balance": "EQUAL_FRONT_AND_BACK_LENGTH",
            "enforcement": "Front and back views MUST have identical vertical height. Back hemline must align horizontally with front hemline."
        },
        "original_specifications": text_prompt,
        "negative_constraints": [
            "NO extended backside length",
            "NO artificial dropped back hem",
            "NO human body parts or face",
            "NO colored backgrounds or borders"
        ]
    }
    return json.dumps(payload, indent=2)
