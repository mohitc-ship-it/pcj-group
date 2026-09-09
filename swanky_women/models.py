from pydantic import BaseModel, Field
from typing import Optional, List, Literal

# # ---------------- HEADER ----------------

class TechPackHeader(BaseModel):
    date: str
    season: str
    collection: str
    style_name: str   # STYLE CODE (single source of truth)
    description: str
    category: str
    brand: str
    size_range: str
    total_order_quantity: Optional[str]
    sample_size_1st: str
    sample_pre_production: Optional[str]
    sample_production: Optional[str]


# # ---------------- COLOR ----------------

class GarmentColorModel(BaseModel):
    color_name: str
    color_hex: str
    pantone_tcx: str   # MUST be marked SUGGESTED

class GarmentColorList(BaseModel):
    colors: List[GarmentColorModel]


# # ---------------- STRUCTURE (STEP 1) ----------------

# class GarmentStructureModel(BaseModel):
#     garment_type: Literal["outerwear", "dress", "top", "bottom", "skirt", "pant"] = Field(..., description="General category of the garment")
#     length: Literal["short", "midi", "long", "cropped", "regular"]
#     front_closure: bool
#     belt_present: bool
#     lapel_present: bool
#     pockets_present: bool
#     sleeves: Literal["long", "short", "sleeveless", "3/4"]
#     slit_present: bool
#     lining_visible: bool # Kept for backward compatibility logic
#     visible_buttons: bool # Kept for backward compatibility logic
#     visible_zipper: bool # Kept for backward compatibility logic


# # ---------------- PAGE 2 ----------------

# class Page2DataModel(BaseModel):
#     details: str


# # ---------------- ACCESSORIES (STEP 2) ----------------

# class AccessoryModel(BaseModel):
#     item: str                       # Button, Snap, Belt Buckle
#     quantity: str                   # "5 pcs", "1.2 m"
#     material: str                   # Metal, Plastic, Polyester
#     dimensions_mm: str              # e.g. "25mm diameter"
#     finish: str                     # Matte, Polished, Antique Brass
#     placement: str                  # Front closure, Shoulder
    
#     # HTML safe fields for backward compatibility view
#     description: Optional[str] = None 
#     qty: Optional[str] = None
#     color: Optional[str] = None
#     position: Optional[str] = None

# class AccessoriesList(BaseModel):
#     accessories: List[AccessoryModel]


# # ---------------- SEAMS (STEP 4) ----------------

# class SeamModel(BaseModel):
#     seam_location: str              # Side seam, Shoulder, Armhole
#     seam_function: Literal["Load bearing", "Structural", "Finish", "Reinforced finish", "Decorative"]
#     seam_type: str                  # Superimposed, Lapped, Bound
#     stitch_type: str                # Lockstitch (301), Overlock (504)
#     allowance_mm: str               # "10mm", "1cm"
#     machine: str                    # Single Needle, 5-Thread Overlock
    
#     # Mapping to existing JSON format for compatibility
#     type: Optional[str] = None
#     symbol: Optional[str] = None
#     allowance: Optional[str] = None
#     title: Optional[str] = None # Some templates might use title/description
#     description: Optional[str] = None 
#     stitch_symbol: Optional[str] = None
#     stitch_size: Optional[str] = None

# class SeamsList(BaseModel):
#     seams: List[SeamModel]


# # ---------------- MEASUREMENTS (STEP 5) ----------------

# class MeasurementModel(BaseModel):
#     pom_name: str                   # Bust, Sleeve Length
#     code: str                       # A, B, C
#     description: str                # How to measure
#     sample_size_value: float        # Base size value
#     tolerance_cm: str               # "+/- 0.5"
    
#     # Aliases to match existing JSON if needed, though exact match is better
#     point_of_measurement: Optional[str] = None
#     measurement_cm: Optional[float] = None

# class MeasurementsList(BaseModel):
#     measurements: List[MeasurementModel]


# # ---------------- FABRICS (STEP 3) ----------------

class FabricModel(BaseModel):
    usage: Literal[
        "Shell",
        "Lining",
        "Pocketing",
        "Belt Fabric",
        "Fusible Interfacing"
    ]
    composition: str                # e.g. "60% Wool / 40% Cotton"
    construction: str               # Woven / Knit / Gabardine
    weight_gsm: str                 # "250 GSM"
    finish: str                     # "Brushed", "None"
    color_pantone: str
    care: str
    
    # HTML safe fields
    description: Optional[str] = None
    color: Optional[str] = None
    position: Optional[str] = None

# class FabricsList(BaseModel):
#     fabrics: List[FabricModel]


# # ---------------- QUALITY ----------------

class FabricQualityStandardModel(BaseModel):
    test: str
    method: str
    requirements: str
    comments: str

class QualityStandardsList(BaseModel):
    quality_standards: List[FabricQualityStandardModel]


# # ---------------- SIZE CHART ----------------

class SizeChartModel(BaseModel):
    pom: str
    s: float
    m: float
    l: float
    xl: float

class SizeChartList(BaseModel):
    size_chart: List[SizeChartModel]

# # ---------------- LEGACY / EXTRA MODELS ----------------
class accoriesModel(BaseModel):
    description: str
    qty: str
    color: str
    position: str




# # NEW METHOD

# # class GarmentAnalysis(BaseModel):
# #     category: str
# #     garment_type: str
# #     sleeve_type: str
# #     length_type: str
# #     fit_type: str
# #     complexity: str
# #     stretch_required: bool
# #     zipper_required: bool


# # class TechPackInput(BaseModel):
# #     front_image: str
# #     back_image: str
# #     detail_images: List[str]

# #     brand: str
# #     collection: str
# #     season: str

# #     market: str  # "US Womenswear"
# #     size_range: List[str]  # ["S","M","L","XL"]
# #     sample_size: str       # "S"

# from pydantic import BaseModel
# from typing import List, Optional, Dict


# # ---------- META ----------
# class Meta(BaseModel):
#     schema_version: str
#     generated_by: str
#     designer_role: str
#     confidence_score: float


# # ---------- INPUT ----------
# class ImageInputs(BaseModel):
#     front: str
#     back: str
#     details: List[str]


# class BrandInput(BaseModel):
#     name: str
#     collection: str
#     season: str


# class SizingInput(BaseModel):
#     market: str
#     size_range: List[str]
#     sample_size: str


# class TechPackInput(BaseModel):
#     images: ImageInputs
#     brand: BrandInput
#     sizing: SizingInput


# # ---------- DERIVED DECISIONS ----------
# class GarmentAnalysis(BaseModel):
#     category: str
#     garment_type: str
#     sleeve_type: str
#     length_type: str
#     fit_type: str
#     complexity: str
#     stretch_required: bool
#     zipper_required: bool


# class FabricLogic(BaseModel):
#     composition: str
#     gsm: str
#     stretch: str
#     reason: str


# class ConstructionLogic(BaseModel):
#     zipper_type: Optional[str]
#     stress_areas: List[str]


# class MeasurementLogic(BaseModel):
#     sample_size: str
#     standard: str
#     tolerance_strategy: Dict[str, str]


# class DerivedDecisions(BaseModel):
#     garment_analysis: GarmentAnalysis
#     fabric_logic: FabricLogic
#     construction_logic: ConstructionLogic
#     measurement_logic: MeasurementLogic


# # ---------- PAGE MODELS ----------
# class Header(BaseModel):
#     date: str
#     season: str
#     collection: str
#     style_name: str
#     description: str
#     category: str
#     brand: str
#     size_range: str
#     total_order_quantity: str
#     sample_size_1st: str
#     sample_pre_production: str
#     sample_production: str


# class Page1(BaseModel):
#     garment_back_view_url: str
#     garment_front_view_url: str
#     style_number: str
#     date: str
#     brand_name: str
#     collection_name: str
#     brand_logo: str


# class Page2(BaseModel):
#     front_image_url: str
#     back_image_url: str
#     detail_image_1_url: str
#     detail_image_2_url: str
#     detail_image_3_url: str
#     detail_image_4_url: str
#     color_name: str
#     color_hex: str
#     details: str


# class Label(BaseModel):
#     image_url: str
#     size: str
#     placement: str


# class Page3(BaseModel):
#     technical_sketch_img: str
#     brand_label: Label
#     size_label: Label
#     care_label: Label
#     label_notes: str


# class Accessory(BaseModel):
#     description: str
#     qty: str
#     color: str
#     position: str


# class Page4(BaseModel):
#     accessories: List[Accessory]


# class Seam(BaseModel):
#     type: str
#     symbol: str
#     allowance: str
#     description: str
#     stitch_type: str
#     stitch_symbol: str
#     stitch_size: str
#     machine: str


# class Page5(BaseModel):
#     seams: List[Seam]


# class Measurement(BaseModel):
#     point_of_measurement: str
#     code: str
#     description: str
#     measurement_cm: float
#     tolerance_cm: str


# class Page6(BaseModel):
#     measurement_image_url: str
#     measurements: List[Measurement]


# class Fabric(BaseModel):
#     description: str
#     color: str
#     position: str


# class QualityStandard(BaseModel):
#     test: str
#     method: str
#     requirements: str
#     comments: str


# class Page7(BaseModel):
#     fabrics: List[Fabric]
#     quality_standards: List[QualityStandard]


# class SizeRow(BaseModel):
#     pom: str
#     m: int
#     l: int
#     xl: int


# class Page8(BaseModel):
#     size_chart: List[SizeRow]


# class WashLabel(BaseModel):
#     composition: str
#     washing_instructions: str
#     bleaching: str
#     drying_instructions: str
#     ironing_instructions: str
#     dry_cleaning: Dict[str, str]
#     label_colors: str


# class Standard(BaseModel):
#     title: str
#     description: str


# class Page9(BaseModel):
#     wash_label: WashLabel
#     care_label_instructions: List[str]
#     other_standards: List[Standard]


# # ---------- FINAL TECH PACK ----------
# class TechPack(BaseModel):
#     meta: Meta
#     inputs: TechPackInput
#     derived_decisions: DerivedDecisions
#     header: Header
#     pages: Dict[str, object]
#     validation: Dict[str, List[str]]


# models.py
from pydantic import BaseModel
from typing import List, Optional, Dict

# ---------- Input ----------
class ImageInputs(BaseModel):
    front: str
    back: Optional[str] = None
    details: Optional[List[str]] = []

class BrandInput(BaseModel):
    name: str
    collection: str
    season: str

class SizingInput(BaseModel):
    market: str  # e.g., "US Womenswear"
    size_range: List[str]
    sample_size: str

class TechPackInput(BaseModel):
    images: ImageInputs
    brand: BrandInput
    sizing: SizingInput
    context_text: Optional[str] = ""


# ---------- Vision Structure (vision-only, audit raw text included) ----------
class GarmentStructureModel(BaseModel):
    garment_category: str  # e.g., Dress, Top, Outerwear
    garment_type: Optional[str] = None
    sleeve_type: Optional[str] = None
    garment_length: Optional[str] = None
    fit_impression: Optional[str] = None
    closure_visibility: Optional[str] = None
    visible_features: List[str] = []
    hem_type: Optional[str] = None
    complexity: str  # Low|Medium|High
    raw_observation_text: Optional[str] = ""


# ---------- Derived Decision pieces ----------
class GarmentAnalysis(BaseModel):
    category: str
    garment_type: str
    sleeve_type: str
    length_type: str
    fit_type: str
    complexity: str
    stretch_required: bool
    zipper_required: bool
    reason: str

class FabricLogic(BaseModel):
    description: str
    composition: str
    gsm_range: str
    stretch: str
    reason: str

class ConstructionLogic(BaseModel):
    seams_summary: str
    zipper_type: Optional[str]
    reason: str

class MeasurementPoint(BaseModel):
    point_of_measurement: str
    code: str
    description: str
    measurement_cm: Optional[float] = None
    tolerance_cm: Optional[str] = None
    value_source: Optional[str] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None

class MeasurementLogic(BaseModel):
    sample_size: str
    measurements: List[MeasurementPoint]
    tolerance_strategy: Dict[str, str]
    reason: str

class Accessory(BaseModel):
    description: str
    qty: str
    color: Optional[str] = ""
    position: Optional[str] = ""
    reason: Optional[str] = ""

class Seam(BaseModel):
    type: str
    symbol: str
    allowance: str
    description: str
    stitch_type: str
    stitch_symbol: str
    stitch_size: str
    machine: str
    reason: Optional[str] = ""

# Page containers
class Page5(BaseModel):
    seams: List[Seam]
    decision_explanation: str

class Page7(BaseModel):
    fabrics: List[Dict]
    quality_standards: List[Dict]
    decision_explanation: str

class VerificationResult(BaseModel):
    valid: bool
    issues: List[str]
    confidence: float
    fix_suggestion: Optional[str] = None
    details: Optional[str] = None


from pydantic import BaseModel, Field
from typing import Literal, List, Optional


class GarmentClassificationModel(BaseModel):
    """
    High-level garment classification used to control
    fabric, construction, measurement, and QC logic.

    This model represents a DESIGN DECISION,
    not a visual description.
    """

    # -------------------------
    # Core Identification
    # -------------------------
    market: Literal["Womenswear", "Menswear", "Kidswear"] = Field(
        ..., description="Primary market segment"
    )

    category: Literal[
        "Dress",
        "Top",
        "Bottom",
        "Skirt",
        "Outerwear",
        "Jumpsuit",
        "Co-ord",
    ] = Field(
        ..., description="Primary garment category"
    )

    sub_category: Optional[str] = Field(
        None,
        description="Optional refined category (e.g. wrap dress, sheath dress, trench coat)"
    )

    # -------------------------
    # Silhouette & Fit
    # -------------------------
    length_type: Literal[
        "Mini",
        "Knee",
        "Midi",
        "Maxi",
        "Cropped",
        "Regular"
    ] = Field(
        ..., description="Garment length classification"
    )

    sleeve_type: Literal[
        "Sleeveless",
        "Short Sleeve",
        "3/4 Sleeve",
        "Long Sleeve"
    ] = Field(
        ..., description="Sleeve length classification"
    )

    fit_type: Literal[
        "Body-hugging",
        "Semi-fitted",
        "Relaxed",
        "Oversized"
    ] = Field(
        ..., description="Overall fit classification"
    )

    # -------------------------
    # Construction Complexity
    # -------------------------
    complexity_level: Literal[
        "Basic",
        "Medium",
        "Complex"
    ] = Field(
        ..., description="Construction complexity based on design features"
    )

    complexity_drivers: List[str] = Field(
        default_factory=list,
        description=(
            "List of features increasing complexity "
            "(e.g. slit, ruching, asymmetry, wrap, pleats)"
        )
    )

    # -------------------------
    # Downstream Control Flags
    # -------------------------
    requires_stretch: Optional[bool] = Field(
        None,
        description="Whether garment likely requires stretch fabric"
    )

    requires_drape: Optional[bool] = Field(
        None,
        description="Whether garment requires fluid drape"
    )

    qc_strictness: Literal[
        "Low",
        "Standard",
        "High"
    ] = Field(
        ..., description="QC tolerance strictness derived from complexity and fit"
    )

    # -------------------------
    # Decision Accountability
    # -------------------------
    reason: str = Field(
        ..., description="Why this classification was chosen"
    )

    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Confidence score for this classification decision"
    )

    requires_confirmation: bool = Field(
        False,
        description=(
            "True if classification has uncertainty and needs human or brand confirmation"
        )
    )


from pydantic import BaseModel, Field
from typing import Literal, Optional, List


class FabricDecisionModel(BaseModel):
    """
    Fabric behavior and performance decision model.

    This model defines HOW the fabric must behave,
    not WHAT the fabric is made of.
    """

    fabric_composition: str = Field(
        ...,
        description="Fabric name and composition required with percentage"
    )

    # -------------------------
    # Fabric Family
    # -------------------------
    fabric_family: str = Field(
        ...,
        description="Broad fabric construction family required"
    )

    # -------------------------
    # Stretch Logic
    # -------------------------
    stretch_required: Literal[
        "None",
        "Low",
        "Medium",
        "High"
    ] = Field(
        ...,
        description="Degree of stretch required for fit and comfort"
    )

    elastane_percentage_range: Optional[str] = Field(
        None,
        description="Recommended elastane range if stretch is required (e.g. 2–4%, 5–8%)"
    )

    # -------------------------
    # Drape & Handfeel
    # -------------------------
    drape_required: Literal[
        "No",
        "Moderate",
        "High"
    ] = Field(
        ...,
        description="Level of fabric fluidity required"
    )

    surface_finish: Literal[
        "Matte",
        "Slight sheen",
        "Glossy",
        "Textured"
    ] = Field(
        ...,
        description="Desired visual surface finish"
    )

    # -------------------------
    # Weight & Seasonality
    # -------------------------
    gsm_range: str = Field(
        ...,
        description="Target fabric weight range based on season and garment type"
    )

    season_suitability: Literal[
        "Summer",
        "Fall",
        "Winter",
        "All-season"
    ] = Field(
        ...,
        description="Seasonal suitability derived from garment usage"
    )

    # -------------------------
    # Stability & Performance
    # -------------------------
    dimensional_stability_required: bool = Field(
        ...,
        description="Whether fabric must resist shrinkage and deformation"
    )

    opacity_required: Literal[
        "Low",
        "Medium",
        "High"
    ] = Field(
        ...,
        description="Required fabric opacity for garment coverage"
    )

    # -------------------------
    # Sustainability & Compliance
    # -------------------------
    sustainability_priority: Optional[
        Literal["Low", "Medium", "High"]
    ] = Field(
        None,
        description="Brand sustainability priority affecting fabric choice"
    )

    restricted_materials: List[str] = Field(
        default_factory=list,
        description="Materials to avoid due to brand or compliance constraints"
    )

    # -------------------------
    # Decision Accountability
    # -------------------------
    reason: str = Field(
        ...,
        description="Why these fabric properties are required for this garment"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this fabric decision"
    )

    requires_confirmation: bool = Field(
        False,
        description="True if final fabric selection needs brand or sourcing confirmation"
    )


from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class SeamDecision(BaseModel):
    """
    Decision-level representation of how a seam area
    should be constructed — without factory codes.
    """

    seam_zone: Literal[
        "Shoulder",
        "Side",
        "Center Back",
        "Center Front",
        "Neckline",
        "Armhole",
        "Sleeve",
        "Cuff",
        "Hem",
        "Waist",
        "Pocket Opening",
        "Slit Opening"
    ] = Field(
        ...,
        description="Physical seam location on the garment"
    )

    seam_function: Literal[
        "Structural",
        "Load-bearing",
        "Stretch-critical",
        "Finish",
        "Decorative",
        "Closure-support"
    ] = Field(
        ...,
        description="Primary functional role of this seam"
    )

    stress_level: Literal[
        "Low",
        "Medium",
        "High"
    ] = Field(
        ...,
        description="Expected stress during wear"
    )

    stretch_sensitivity: Literal[
        "None",
        "Low",
        "High"
    ] = Field(
        ...,
        description="Sensitivity to stretch based on fit and movement"
    )

    visibility: Literal[
        "High",
        "Medium",
        "Low"
    ] = Field(
        ...,
        description="Whether the seam is visually prominent"
    )

    durability_priority: Literal[
        "Low",
        "Medium",
        "High"
    ] = Field(
        ...,
        description="Durability requirement for this seam"
    )

    recommended_strategy: str = Field(
        ...,
        description=(
            "Human-readable construction strategy "
            "(e.g. 'Stretch-compatible structural seam with clean finish')"
        )
    )

    reason: str = Field(
        ...,
        description="Why this construction strategy is required for this seam zone"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in this construction decision"
    )

    requires_confirmation: bool = Field(
        False,
        description="True if fabric finalization or brand standards may alter this decision"
    )


class ConstructionDecisionModel(BaseModel):
    """
    High-level construction decision model.

    This model defines HOW the garment should be built,
    before translating into factory-specific instructions.
    """

    seam_decisions: List[SeamDecision] = Field(
        ...,
        description="List of seam-level construction decisions"
    )

    overall_construction_complexity: Literal[
        "Basic",
        "Medium",
        "Complex"
    ] = Field(
        ...,
        description="Overall construction complexity of the garment"
    )

    key_risk_areas: List[str] = Field(
        default_factory=list,
        description=(
            "Areas requiring special attention during construction "
            "(e.g. stretch seams, slit openings, wrap overlap)"
        )
    )

    construction_notes: Optional[str] = Field(
        None,
        description="Additional global construction guidance"
    )

    reason: str = Field(
        ...,
        description="Why this construction approach was chosen overall"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for overall construction strategy"
    )

    requires_confirmation: bool = Field(
        False,
        description="True if construction approach depends on unresolved decisions"
    )


from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class MeasurementPointDecision(BaseModel):
    """
    Decision-level definition of a Point of Measurement (POM).

    This model defines WHAT to measure and HOW important it is,
    without forcing a final numeric value.
    """

    pom_name: str = Field(
        ...,
        description="Standard industry name of the measurement point (e.g. Chest, Waist, Hip)"
    )

    pom_code: Optional[str] = Field(
        None,
        description="POM reference code used in tech packs (e.g. A, B, C)"
    )

    pom_type: Literal[
        "Circumference",
        "Length",
        "Width",
        "Depth"
    ] = Field(
        ...,
        description="Type of measurement, used to determine tolerance logic"
    )

    body_zone: Literal[
        "Upper Body",
        "Torso",
        "Lower Body",
        "Sleeve",
        "Neck",
        "Hem",
        "Closure Area"
    ] = Field(
        ...,
        description="Anatomical or garment zone this measurement belongs to"
    )

    measurement_priority: Literal[
        "Critical",
        "Important",
        "Reference"
    ] = Field(
        ...,
        description=(
            "How critical this measurement is for fit approval "
            "(Critical = must pass QC, Reference = informational)"
        )
    )

    tolerance_range_cm: str = Field(
        ...,
        description="Acceptable tolerance range based on industry standards (e.g. ±1.0–1.5 cm)"
    )

    value_source: Literal[
        "Brand Fit Block",
        "Industry Reference",
        "Derived from Similar Style",
        "TBD / To Be Confirmed"
    ] = Field(
        ...,
        description="Source from which final numeric value should be taken"
    )

    grading_applicability: Literal[
        "Graded",
        "Not Graded"
    ] = Field(
        ...,
        description="Whether this POM should be graded across sizes"
    )

    reason: str = Field(
        ...,
        description="Why this measurement point is required for this garment"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in this measurement decision"
    )

    requires_confirmation: bool = Field(
        False,
        description="True if numeric value or tolerance requires human/brand confirmation"
    )


class MeasurementDecisionModel(BaseModel):
    """
    High-level measurement planning model.

    This model defines the MEASUREMENT STRATEGY
    before numbers are finalized.
    """

    sample_size: str = Field(
        ...,
        description="Sample size on which measurements will be based (e.g. S, M)"
    )

    market: Literal[
        "US Women",
        "EU Women",
        "UK Women",
        "Menswear"
    ] = Field(
        ...,
        description="Sizing market governing measurement standards"
    )

    measurement_points: List[MeasurementPointDecision] = Field(
        ...,
        description="List of all defined Points of Measurement"
    )

    grading_rule_summary: str = Field(
        ...,
        description="High-level explanation of how grading will be applied across sizes"
    )

    overall_fit_risk: Literal[
        "Low",
        "Medium",
        "High"
    ] = Field(
        ...,
        description="Risk of fit issues based on garment complexity and fit type"
    )

    measurement_notes: Optional[str] = Field(
        None,
        description="Additional notes for pattern maker or QC team"
    )

    reason: str = Field(
        ...,
        description="Why this measurement strategy was chosen overall"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for the overall measurement plan"
    )

    requires_confirmation: bool = Field(
        False,
        description="True if final measurements cannot be locked without further input"
    )


from pydantic import BaseModel, Field
from typing import List, Optional, Literal


# -------------------------------------------------
# FABRIC (FACTORY LEVEL)
# -------------------------------------------------

class FactoryFabric(BaseModel):
    usage: Literal[
        "Shell",
        "Lining",
        "Pocketing",
        "Belt Fabric",
        "Interfacing"
    ]

    description: str = Field(
        ...,
        description="Factory-readable fabric description including composition and construction"
    )

    composition: str = Field(
        ...,
        description="Fiber composition with percentages"
    )

    construction: Literal[
        "Woven",
        "Knit",
        "Bias-cut Woven",
        "Non-woven"
    ]

    weight_gsm: str = Field(
        ...,
        description="Fabric weight range in GSM"
    )

    stretch: Literal[
        "None",
        "Low",
        "Medium",
        "High"
    ]

    finish: Optional[str] = Field(
        None,
        description="Surface finish (e.g. matte, brushed)"
    )

    color: str = Field(
        ...,
        description="Color name or Pantone reference"
    )

    position: str = Field(
        ...,
        description="Where fabric is used on garment"
    )

    justification: str = Field(
        ...,
        description="Why this fabric was selected based on design decisions"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0
    )

    requires_confirmation: bool = False


# -------------------------------------------------
# SEAMS (FACTORY LEVEL)
# -------------------------------------------------

# -------------------------------------------------
# MEASUREMENTS (FACTORY LEVEL)
# -------------------------------------------------

# -------------------------------------------------
# ACCESSORIES / TRIMS
# -------------------------------------------------



# -------------------------------------------------
# CARE & LABELING
# -------------------------------------------------



# -------------------------------------------------
# FINAL AGGREGATE
# -------------------------------------------------



class StrictModel(BaseModel):
    class Config:
        extra = "forbid"


class FactoryFabric(StrictModel):
    usage: Literal[
        "Shell",
        "Lining",
        "Pocketing",
        "Belt Fabric",
        "Interfacing",
        "Interlining"
    ]

    description: str = Field(
        ..., description="Factory-readable fabric description"
    )

    composition: str = Field(
        ..., description="Fiber composition with percentages"
    )

    construction: Literal[
        "Woven",
        "Knit",
        "Bias-cut Woven",
        "Non-woven"
    ]

    weight_gsm: str

    stretch: Literal[
        "None",
        "Low",
        "Medium",
        "High"
    ]

    finish: Optional[str]

    color: str

    position: str

    justification: str

    confidence: float = Field(..., ge=0.0, le=1.0)

    requires_confirmation: bool = False


class FactorySeam(StrictModel):
    seam_location: str

    seam_type: str

    seam_symbol: Optional[str]

    seam_allowance_mm: str

    description: str

    stitch_type: str

    stitch_symbol: str

    stitch_size: str

    machine_type: str

    justification: str

    confidence: float = Field(..., ge=0.0, le=1.0)

    requires_confirmation: bool = False


class FactoryMeasurement(StrictModel):
    point_of_measurement: str

    pom_code: Optional[str]

    description: str

    sample_size_value_cm: Optional[float]

    tolerance_cm: str

    grading: Literal[
        "Graded",
        "Not Graded"
    ]

    value_source: str

    justification: str

    confidence: float = Field(..., ge=0.0, le=1.0)

    requires_confirmation: bool = False


class FactoryAccessory(StrictModel):
    item_description: str

    quantity: str

    material: Optional[str]

    dimensions: Optional[str]

    color: Optional[str]

    placement: str

    justification: str

    confidence: float = Field(..., ge=0.0, le=1.0)

    requires_confirmation: bool = False


class DryCleaningInstruction(StrictModel):
    line_1: Optional[str]
    line_2: Optional[str]


class FactoryCareLabel(StrictModel):
    composition: str

    washing_instructions: str

    bleaching: str

    drying_instructions: str

    ironing_instructions: str

    dry_cleaning: Optional[DryCleaningInstruction]

    standards: List[str]

    justification: str

    confidence: float = Field(..., ge=0.0, le=1.0)

    requires_confirmation: bool = False

class FactoryInstructionModel(StrictModel):
    """
    FINAL factory-ready instruction set.
    This is the ONLY model allowed to populate tech pack tables.
    """

    fabrics: List[FactoryFabric]

    seams: List[FactorySeam]

    measurements: List[FactoryMeasurement]

    accessories: List[FactoryAccessory]

    care_label: FactoryCareLabel

    global_notes: Optional[str]

    overall_confidence: float = Field(..., ge=0.0, le=1.0)

    requires_confirmation: bool = False
