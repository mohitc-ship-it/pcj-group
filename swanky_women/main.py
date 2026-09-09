import json
import datetime
from copy import deepcopy

from llm import analyze_images, llm_structured, llm_query
from generate import generatePdf
from utils import extract_clothing_palette, map_json, combine_images_horizontally, split_into_grids, recommend_colors_from_images
from imageGen import generate_image

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
    palette = recommend_colors_from_images(images[0],images[1])

    # palette = extract_clothing_palette(images[0])

    prompt = f"""
ROLE: Textile Color Matching Specialist  

You are working for a **fashion brand color lab**.  
Your job is to identify the **primary garment color** from the provided images and palette.

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

You must determine:

1. The **single main garment color**
   - The color that covers the **largest surface area** of the garment
   - Ignore:
     • Shadows
     • Highlights
     • Texture variations
     • Lighting bias
     • Folds and wrinkles

2. The **best matching Pantone TCX** for that color
   - TCX = textile (fabric) system
   - This is an **approximation**, not a guarantee

────────────────────────────────────────────
COLOR SELECTION RULES
────────────────────────────────────────────

You must choose the color that:
• Is present on the majority of the garment
• Matches the extracted palette
• Is NOT background
• Is NOT a shadow
• Is NOT a trim or small detail

If two colors are close:
→ Pick the more neutral, dominant, mid-tone one

────────────────────────────────────────────
PANTONE RULES
────────────────────────────────────────────

You must:
• Provide a Pantone TCX code (e.g., 19-4052 TCX)
• Mark it as **SUGGESTED**
• Base it on visual proximity to the HEX value
• Never claim it is exact

You must NOT:
• Use Pantone Solid Coated (PMS)
• Use Pantone C/U
• Guarantee accuracy

────────────────────────────────────────────
OUTPUT
────────────────────────────────────────────

Return List of **GarmentColorModel** in JSON with:

• color_name  
• hex  
• pantone_tcx  
• confidence (0–1)  
• justification  
• pantone_accuracy_note = "Suggested – visual approximation only"

showcasing top 5-8 possible pantone colors (most nearest for manufacturer's understanding)

If confidence < 0.7 → requires_confirmation = true
"""""

    print(f"[DEBUG] extract_garment_color: palette length={len(palette) if hasattr(palette,'__len__') else 'N/A'}")
    # only print a small sample of the prompt to avoid huge logs
    print(f"[DEBUG] extract_garment_color: calling analyze_images + llm_structured with prompt preview: {prompt[:200].replace('\n',' ')}...")
    result = llm_structured(
        analyze_images(images, prompt),
        GarmentColorList
    ).model_dump()
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
• Straight  
• Curved  
• Asymmetrical  
• Raw edge  
• Finished edge  

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
• hem_type  
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

    vision_text = analyze_images(images, prompt)
    print(f"[DEBUG] vision_agent: analyze_images returned text length={len(vision_text) if vision_text else 0}")
    structure = llm_structured(vision_text, GarmentStructureModel).model_dump()
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
    classification = llm_structured(prompt, GarmentClassificationModel).model_dump()
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
    fabric = llm_structured(prompt, FabricDecisionModel).model_dump()
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
    construction = llm_structured(prompt,ConstructionDecisionModel).model_dump()
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
    return llm_structured(prompt, MeasurementDecisionModel).model_dump()

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
    measurement = llm_structured(prompt, MeasurementDecisionModel).model_dump()
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
- seam_type: Superimposed Seam, Edge Finish, Lapped Seam, etc
- seam_symbol: SSa-1, SSb-2, SSa, EFa, EFb, LSb, etc (each seam MUST have a DISTINCT symbol)
- seam_allowance_mm: realistic values (6-15mm range typically)
- description: Shoulder Seam, Side Seam, Hem stitching, Center back zipper insertion, etc
- stitch_type: Lockstitch (301), Overlock (504), Coverstitch (406), etc
- stitch_symbol: 301, 504, 406, etc
- stitch_size: 2-4mm typically
- machine_type: Single needle machine, 4-thread Overlock, Coverstitch Machine, Invisible Zipper Foot, etc

REFERENCE EXAMPLE (Women's Asymmetrical Dress):
1. Superimposed Seam | SSa-1 | 10mm | Shoulder Seam | Lockstitch (301) | 301 | 3mm | Single needle machine
2. Superimposed Seam | SSb-2 | 6mm | Side Seam | Lockstitch (301) | 301 | 3mm | Single needle machine
3. Superimposed Seam | SSa | 8mm | Side seams, shoulder seams, center back seam | Overlock (504) | 504 | 4mm | 4-thread Overlock
4. Edge Finish | EFa | 10mm | Hem stitching, neckline topstitch (if needed) | Lockstitch (301) | 301 | 2-2.5mm | Lockstitch Machine
5. Edge Finish Seam | EFb | 10mm | Hem (if lined or unlined stretch hem) | Coverstitch (406) | 406 | 3mm | Coverstitch Machine
6. Lapped Seam (invisible zip) | LSb | 10mm | Center back zipper insertion | Lockstitch (301) | 301 | - | Invisible Zipper Foot

────────────────────────────────────────────
SECTION 3 — MEASUREMENTS
────────────────────────────────────────────

Use REAL US Women's size S values for the garment category.
These must be HALF-BODY measurements (not full circumference) for chest, waist, hip.

CRITICAL MEASUREMENT REFERENCE (US Women's Size S):
- Dress/Top: Chest=84cm, Waist=68cm, Hips=92cm, Shoulder-to-Shoulder=37cm
- Jacket/Outerwear: Chest=88-92cm, Waist=72-76cm, Shoulder=38-40cm
- Body Length: Dress maxi=130-140cm, Dress midi=100-115cm, Jacket hip-length=58-65cm

Tolerances must use ± format with SPECIFIC values:
- Circumferences: ±1.27 cm
- Lengths: ±0.64 to ±0.67 cm
- Sleeve: ±0.27 cm
- Width measurements: ±0.64 cm

Include garment-specific POMs:
- Dresses: include Slit Length if slit exists, Dress Length (front AND back if asymmetric)
- Jackets: include Across Shoulder, Pocket Opening Width
- All: Chest, Waist, Hips, Sleeve Length, Armhole Depth

Each measurement MUST have a UNIQUE justification — do NOT use the same justification for all.

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
- Concealed/Invisible Zipper (22-24 cm) — if closure visible/needed
- Buttons — specify exact count matching what is VISIBLE in image
- Interlining/Fusible — if structured collar/cuffs exist
- Decorative trim — only if visible

Count accessories by CAREFULLY examining the images. If 4 buttons visible, say 4, NOT 5 or 6.

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
    factory = llm_structured(
        analyze_images(images, prompt),
        FactoryInstructionModel
    ).model_dump()
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
# • Value
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
    verification = llm_structured(prompt, VerificationResult).model_dump()
    print(f"[DEBUG] verifier_agent: verification result -> valid={verification.get('valid')} confidence={verification.get('confidence')}")
    return verification


# =========================================================
# MAIN PIPELINE
# =========================================================

def generate_techpack(images, context,generate=False):

    # 1. Load master
    with open("data/master.json") as f:
        master = deepcopy(json.load(f))
    print(f"[DEBUG] generate_techpack: loaded master.json, top-level keys={list(master.keys())}")
    for i in range(1, 10):
        ensure_page(master, f"page_{i}")

    # 2. Header
    header_prompt = f"""
    Generate FACTORY tech pack header.
    
    Logic for style name generation : [Brand/Collection] – [Season] – [Year] – [Garment Type]
    Example of style_name: JCC-S-FA25-DRS
    
    Inputs:
    {context}
    
    Date: {datetime.datetime.now().strftime("%d/%m/%Y")}

    description should be one liner
    such as "women's asymmetric dress"
    """

    print("trying for header")
    header = llm_structured(
        header_prompt,
        TechPackHeader
    ).model_dump()
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

    first_page_logo_prompt = f"""replace swanky by collection name {master['page_1']['brand_name']},also replace collection name to {master['page_1']['collection_name']}"""
    
    if generate==True:
        generate_image(first_page_logo_prompt,"assets/first_page_logo.png","assets/first_page_logo_current.png")

    master["page_1"]["brand_logo"] = "assets/first_page_logo_current.png"

    # 4. Color
    colors = extract_garment_color(images)
    colors = colors['colors']
    master['page_2']['optional_colors'] = colors
    color = colors[0]
    master["page_2"].update(color)
    print(f"[DEBUG] generate_techpack: extracted color -> name={color.get('color_name')} hex={color.get('hex')}")

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
        "sample_size": "M", # Defaulting to S as per designer mindset "Sample size = S"
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
    page2_details = analyze_images(images, page2_prompt)
    print("page2 details are", page2_details)
    
    master["page_2"].update({
        "details": page2_details,
        "front_image_url": front_img,
        "back_image_url": back_img,
    })
    
    combined_image = combine_images_horizontally(images,"assets/combined.png")
    # Determine grid height based on garment category
    garment_cat = classification.get('category', '').lower()
    if garment_cat in ('outerwear',) or 'jacket' in garment_cat or 'coat' in garment_cat:
        grid_height = 1400
    else:
        grid_height = 575
    images = split_into_grids(combined_image,"assets",grid_height=grid_height,extra_width=190)

    # Use front image as fallback if not enough detail grids
    DEFAULT_IMAGE = front_img

    # Ensure at least 4 images, fill missing with front image
    safe_images = images + [DEFAULT_IMAGE] * (4 - len(images))

    master["page_2"].update({
        "detail_image_1_url": safe_images[0],
        "detail_image_2_url": safe_images[1],
        "detail_image_3_url": safe_images[2],
        "detail_image_4_url": safe_images[3],
        "optional_image_urls": images  # keep original list
    })


    # page 3

    technical_sketch_prompt = f"""

Convert the provided image of a model wearing a garment into a professional fashion technical sketch suitable for a production tech pack.

Output Requirements:
- Create clean black-and-white vector-style line art
- Show front and back
- White background, no color, no shading, no textures
- Garment only (remove model facial and body features)

Annotation & Labeling:
- Add clear callout labels and leader lines
- Label all construction, seam, and design details provided below
- Use industry-standard fashion technical drawing conventions
- Layout should look like it was created by a senior fashion designer

Don't draw any lines or zippers or buttons or any other details , untill specified in accesories.

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

    if generate:
        master['page_3']['technical_sketch_img'] = generate_image(technical_sketch_prompt, "assets/combined.png","assets/technical_sketch.png")
    else:
        master['page_3']['technical_sketch_img'] = "assets/technical_sketch.png"

    brand_label_prompt = f"""Create a brand label for a garment with:
    - Brand/Collection name: {master['page_1']['collection_name']}
    - Garment description: {master['header']['description']}
    - Website: https://jccobrand.com/

    Replace any existing text on the label with the above details.
    Keep the same clean, minimal label design style.
    """

    if generate:
        master['page_3']['brand_label_img'] = generate_image(brand_label_prompt, "assets/brand_label.png","assets/brand_label_final.png")
    else:
        print("going in else for brand label")
        master['page_3']['brand_label_img'] = "assets/brand_label_final.png"

    care_label_prompt = f"""generate care label for garment with fabric description: {factory_output.get("fabrics", [])}
        accessories include {factory_output.get("accessories", [])}
            and dress description as {page2_details}"""

    if generate:
        master['page_3']['care_label_img'] = generate_image(care_label_prompt, "assets/care_label.png","assets/care_label_final.png")
    else:
        print("going in else for care label")
        master['page_3']['care_label_img'] = "assets/care_label_final.png"



    measurement_diagram = f"""A professional fashion technical flat (tech pack measurement diagram) of given image garment, shown in front view and back view side-by-side on a clean white background.

    Draw everything using thin black vector CAD-style lines with no shading, no textures, and no colors.

    On the front view, include red technical measurement guides:

    horizontal, vertical, and diagonal double-arrow dimension lines

    dots at measurement points

    empty letter placeholders (A, B, C, D, E, F…) placed near each measurement line

    Do NOT add text labels or values — only the letters should appear so that labels can be added later.

    Layout must look like a factory-ready fashion tech pack page used for clothing manufacturing.

    measurement details:
    {master['page_6']['measurements']}"""

    if generate:
        master['page_6']['measurement_image_url'] = generate_image(measurement_diagram, combined_image,"assets/measurement_diagram.png")
    else:
        master['page_6']['measurement_image_url'] = "assets/measurement_diagram.png"

    
    master["page_4"]["accessories"] = factory_output.get("accessories", [])
    master["page_5"]["seams"] = factory_output.get("seams", [])
    master["page_6"]["measurements"] = factory_output.get("measurements", [])
    master["page_7"]["fabrics"] = factory_output.get("fabrics", [])
    
    # # Page 7 Quality Standards (Agent call)
    # master["page_7"]["quality_standards"] = llm_structured(
    #     f"""Generate quality standards for this {classification['category']}. Return JSON only.
    #     example quality standards are Dimensional Stability , Color Fastness to Washing, Color Fastness to Rubbing, Flammability (optional), etc could be possible based on fabric and garment information.
    #     """,
    #     QualityStandardsList
    # ).model_dump()["quality_standards"]

    master["page_7"]["quality_standards"] = llm_structured(
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
    , QualityStandardsList
).model_dump()["quality_standards"]


    # Page 8 Size Chart (Agent call based on measurements)
    # master["page_8"]["size_chart"] = llm_structured(
    #     f"Generate size chart for {classification['market']} {classification['category']} Size {classification['size_range'] if 'size_range' in classification else 'S-XL'}. Return JSON only.",
    #     SizeChartList
    # ).model_dump()["size_chart"]

    master["page_8"]["size_chart"] = llm_structured(
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
        SizeChartList
    ).model_dump()["size_chart"]

    
    # Page 9 Care
    master["page_9"]["wash_label"] = factory_output.get("care_label", {})
    master['page_9']['wash_care_label_img'] = master['page_3']['care_label_img']
    ensure_page_9_contract(master["page_9"])
    

    final_json = map_json(master)


    # 9. Save
    with open("data/master_filled.json", "w") as f:
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