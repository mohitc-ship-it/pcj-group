import cv2
import numpy as np

import cv2
import numpy as np
from sklearn.cluster import KMeans

def extract_clothing_palette(
    image_path,
    k=10,
    white_thresh=240,
    min_cluster_ratio=0.03
):
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)

    pixels_rgb = img.reshape((-1, 3))
    pixels_hsv = hsv.reshape((-1, 3))

    # 🔹 Remove white & near-black
    mask = ~(
        ((pixels_hsv[:,1] < 20) & (pixels_hsv[:,2] > 220)) |
        (pixels_hsv[:,2] < 20)
    )

    pixels_rgb = pixels_rgb[mask]

    if len(pixels_rgb) < 500:
        return []

    kmeans = KMeans(n_clusters=k, n_init=10)
    labels = kmeans.fit_predict(pixels_rgb)
    centers = kmeans.cluster_centers_

    total = len(labels)
    palette = []

    for i in range(k):
        count = np.sum(labels == i)
        ratio = count / total

        if ratio < min_cluster_ratio:
            continue

        r, g, b = centers[i].astype(int)
        hex_color = f"#{r:02X}{g:02X}{b:02X}"

        palette.append({
            "hex": hex_color,
            "ratio": round(ratio, 3)
        })

    # Sort by dominance
    palette.sort(key=lambda x: x["ratio"], reverse=True)
    return palette

# print(extract_clothing_palette("assets/back.png"))


def adapt_accessories_for_html(accessories):
    return [
        {
            "description": a["description"],
            "qty": a["quantity"],
            "color": a.get("color", ""),
            "position": a["position"]
        }
        for a in accessories
    ]


def adapt_fabrics_for_html(fabrics):
    return [
        {
            "description": f["description"],
            "color": f["color_pantone"],
            "position": f["position"]
        }
        for f in fabrics
    ]


# print(extract_clothing_palette("assets/front.png"))


import numpy as np
from colormath.color_objects import sRGBColor, LabColor
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000

"""
garment_color_from_images.py

INPUT:
- front image path
- back image path

OUTPUT:
- Top garment HEX colors
- Confidence score
- Color family
- Optional print-Pantone approximation (non-binding)

Safe for tech packs & manufacturing.
"""

import math
import pickle
import colorsys
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
from typing import List, Dict, Tuple, Optional
from colormath.color_objects import sRGBColor, LabColor
from colormath.color_conversions import convert_color


# ---- FIX for colormath + numpy>=2.0 compatibility ----
import numpy as _np

if not hasattr(_np, "asscalar"):
    def _asscalar(a):
        return a.item()
    _np.asscalar = _asscalar
# -----------------------------------------------------

from colormath.color_diff import delta_e_cie2000

# --------------------------------------------------
# VERIFIED PANTONE TCX LOOKUP (replaces LLM guessing)
# --------------------------------------------------
_PANTONE_TCX_CACHE = None

def load_pantone_tcx():
    """Load the Pantone TCX dataset from data/pantone_tcx.json (cached)."""
    global _PANTONE_TCX_CACHE
    if _PANTONE_TCX_CACHE is not None:
        return _PANTONE_TCX_CACHE
    import json, os
    data_path = os.path.join(os.path.dirname(__file__), "data", "pantone_tcx.json")
    with open(data_path, "r") as f:
        _PANTONE_TCX_CACHE = json.load(f)
    return _PANTONE_TCX_CACHE

def nearest_pantone_tcx(hex_color: str, top_k: int = 3) -> list:
    """
    Given a hex color (e.g. '#2C3E50'), return the top_k nearest
    Pantone FHI TCX colors by CIE2000 Delta-E distance.
    Returns: [{ code, name, hex, delta_e }, ...]  ← ground truth, NOT an LLM guess.
    """
    pantones = load_pantone_tcx()
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    target_lab = rgb_to_lab((r, g, b))

    results = []
    for p in pantones:
        pr = int(p["hex"][1:3], 16)
        pg = int(p["hex"][3:5], 16)
        pb = int(p["hex"][5:7], 16)
        p_lab = rgb_to_lab((pr, pg, pb))
        dE = float(delta_e_cie2000(target_lab, p_lab))
        results.append({
            "code": p["code"],
            "name": p["name"],
            "hex": p["hex"],
            "delta_e": round(dE, 2),
        })

    return sorted(results, key=lambda x: x["delta_e"])[:top_k]

# --------------------------------------------------
# COLOR UTILITIES
# --------------------------------------------------
def rgb_to_lab(rgb: Tuple[int,int,int]) -> LabColor:
    srgb = sRGBColor(rgb[0]/255, rgb[1]/255, rgb[2]/255)

    return convert_color(srgb, LabColor)

def rgb_to_hsv(rgb: Tuple[int,int,int]):
    r,g,b = [x/255 for x in rgb]
    h,s,v = colorsys.rgb_to_hsv(r,g,b)
    return h*360, s, v

def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)

# --------------------------------------------------
# IMAGE → VALID GARMENT PIXELS
# --------------------------------------------------
def extract_valid_pixels(image_path: str) -> np.ndarray:
    img = Image.open(image_path).convert("RGB")
    pixels = np.array(img).reshape(-1, 3)

    valid = []
    for r,g,b in pixels:
        # Remove white / background
        if r > 245 and g > 245 and b > 245:
            continue

        h,s,v = rgb_to_hsv((r,g,b))
        if s < 0.18:   # remove lining / beige / skin
            continue

        lab = rgb_to_lab((r,g,b))
        if lab.lab_l < 12:  # remove deep shadows (was 30, which deleted navy/black garments!)
            continue

        valid.append((r,g,b))

    return np.array(valid)

# --------------------------------------------------
# CLUSTER PIXELS (LAB SPACE)
# --------------------------------------------------
def cluster_pixels(pixels: np.ndarray, n_clusters=8):
    lab_pixels = np.array([
        [rgb_to_lab(tuple(p)).lab_l,
         rgb_to_lab(tuple(p)).lab_a,
         rgb_to_lab(tuple(p)).lab_b]
        for p in pixels
    ])

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
    labels = kmeans.fit_predict(lab_pixels)

    clusters = {}
    for label, rgb in zip(labels, pixels):
        clusters.setdefault(label, []).append(rgb)

    results = []
    for rgbs in clusters.values():
        rgbs = np.array(rgbs)
        avg_rgb = np.mean(rgbs, axis=0).astype(int)
        results.append({
            "rgb": tuple(avg_rgb),
            "hex": rgb_to_hex(tuple(avg_rgb)),
            "weight": len(rgbs)
        })

    return results

# --------------------------------------------------
# MERGE FRONT + BACK CLUSTERS
# --------------------------------------------------
def merge_clusters(front, back, delta_e_thresh=5):
    merged = []

    for src in front + back:
        rgb = src["rgb"]
        lab = rgb_to_lab(rgb)
        weight = src["weight"]

        placed = False
        for m in merged:
            dE = delta_e_cie2000(
                LabColor(lab.lab_l, lab.lab_a, lab.lab_b),
                LabColor(*m["lab"])
            )
            if dE < delta_e_thresh:
                m["sum_rgb"] += np.array(rgb) * weight
                m["weight"] += weight
                placed = True
                break

        if not placed:
            merged.append({
                "sum_rgb": np.array(rgb) * weight,
                "weight": weight,
                "lab": [lab.lab_l, lab.lab_a, lab.lab_b]
            })

    final = []
    for m in merged:
        avg_rgb = (m["sum_rgb"] / m["weight"]).astype(int)
        final.append({
            "rgb": tuple(avg_rgb),
            "hex": rgb_to_hex(tuple(avg_rgb)),
            "weight": m["weight"]
        })

    return final

# --------------------------------------------------
# RANK + CONFIDENCE
# --------------------------------------------------
def rank_colors(colors: List[Dict], top_n=6):
    colors = sorted(colors, key=lambda x: x["weight"], reverse=True)
    max_w = colors[0]["weight"]

    return [{
        "hex": c["hex"],
        "rgb": c["rgb"],
        "confidence": round(c["weight"]/max_w, 3)
    } for c in colors[:top_n]]

# --------------------------------------------------
# COLOR FAMILY (DESIGNER FRIENDLY)
# --------------------------------------------------
def color_family(hex_color: str):
    r = int(hex_color[1:3],16)
    g = int(hex_color[3:5],16)
    b = int(hex_color[5:7],16)
    h,s,v = rgb_to_hsv((r,g,b))

    if 40 <= h <= 60:
        return "Golden / Mustard Yellow"
    if 30 <= h < 40:
        return "Spicy Mustard (Orange-biased)"
    if 60 < h <= 90:
        return "Olive Yellow"
    return "Other"

# --------------------------------------------------
# OPTIONAL PRINT PANTONE FALLBACK
# --------------------------------------------------
def load_print_pantone(pickle_path):
    raw = pickle.load(open(pickle_path,"rb"))
    pantones = []
    for k,v in raw.items():
        try:
            r,g,b = map(int, k.split(", "))
            pantones.append({"rgb":(r,g,b),"code":v})
        except:
            pass
    return pantones

def approx_print_pantone(hex_color, pantones, top_k=3):
    target_lab = rgb_to_lab((
        int(hex_color[1:3],16),
        int(hex_color[3:5],16),
        int(hex_color[5:7],16)
    ))
    results = []
    for p in pantones:
        p_lab = rgb_to_lab(p["rgb"])
        dE = delta_e_cie2000(target_lab, p_lab)
        results.append({"pantone":p["code"], "delta_e":round(dE,2)})
    return sorted(results, key=lambda x:x["delta_e"])[:top_k]

# --------------------------------------------------
# SPLIT PALETTE INTO N DISTINCT COLOR GROUPS
# --------------------------------------------------
def cluster_into_color_groups(top_colors: List[Dict], n_groups: int = 2, min_lab_distance: float = 22.0) -> List[List[Dict]]:
    """
    Splits ranked pixel colors into N visually distinct groups.
    Uses CIELAB Delta-E distance to separate colors that are perceptually far apart.
    Returns a list of groups, each group is a list of color dicts.
    """
    if not top_colors:
        return []

    # Each group starts empty. We assign each color to the nearest group centroid.
    # Seed with the most dominant color as the first group centroid.
    groups = [[top_colors[0]]]
    group_centroids_lab = [rgb_to_lab(top_colors[0]["rgb"])]

    for color in top_colors[1:]:
        color_lab = rgb_to_lab(color["rgb"])
        # Find nearest existing group
        min_dist = float("inf")
        nearest_group_idx = 0
        for i, centroid_lab in enumerate(group_centroids_lab):
            dE = delta_e_cie2000(
                LabColor(color_lab.lab_l, color_lab.lab_a, color_lab.lab_b),
                LabColor(centroid_lab.lab_l, centroid_lab.lab_a, centroid_lab.lab_b)
            )
            if dE < min_dist:
                min_dist = dE
                nearest_group_idx = i

        if min_dist >= min_lab_distance and len(groups) < n_groups:
            # This color is far enough from all existing groups — start a new group
            groups.append([color])
            group_centroids_lab.append(color_lab)
        else:
            # Assign to nearest group
            groups[nearest_group_idx].append(color)

    return groups


# --------------------------------------------------
# 🔥 MAIN ENTRY FUNCTION
# --------------------------------------------------
def recommend_colors_from_images(
    front_image: str,
    back_image: str,
    top_n=6,
    print_pantone_pickle: Optional[str]=None
):
    front_pixels = extract_valid_pixels(front_image)
    back_pixels = extract_valid_pixels(back_image)

    front_clusters = cluster_pixels(front_pixels)
    back_clusters = cluster_pixels(back_pixels)

    merged = merge_clusters(front_clusters, back_clusters)
    top_colors = rank_colors(merged, top_n)

    # output = {
    #     "color_family": color_family(top_colors[0]["hex"]),
    #     "top_hex_candidates": top_colors,
    #     "manufacturing_note":
    #         "Match to Pantone FHI (TCX) book under D65 lighting and approve via lab dip."
    # }

    # if print_pantone_pickle:
    #     pantones = load_print_pantone(print_pantone_pickle)
    #     output["approx_print_pantone"] = [
    #         {
    #             "hex": c["hex"],
    #             "matches": approx_print_pantone(c["hex"], pantones)
    #         }
    #         for c in top_colors
    #     ]
    #     output["note"] = "Print Pantone is NON-BINDING and NOT TCX."

    return top_colors


def render_pantone_swatches(pantone_options: list, output_path: str = None) -> str:
    """
    Renders a grid of solid Pantone color swatches as a labeled PNG image.
    Each swatch is a 200x200px solid block with the Pantone code and name below it.

    Args:
        pantone_options: list of {"code": ..., "name": ..., "hex": ...} dicts
        output_path: optional path to save; auto-generates temp file if None

    Returns:
        Absolute path to the saved PNG.
    """
    import os, tempfile, math
    from PIL import Image, ImageDraw

    SWATCH_W = 200
    SWATCH_H = 200
    LABEL_H  = 55
    COLS     = 5
    PAD      = 12
    BG       = (230, 230, 230)
    TEXT_COL = (30, 30, 30)

    n    = len(pantone_options)
    rows = math.ceil(n / COLS) if n else 1
    img_w = COLS * (SWATCH_W + PAD) + PAD
    img_h = rows * (SWATCH_H + LABEL_H + PAD) + PAD

    canvas = Image.new("RGB", (img_w, img_h), BG)
    draw   = ImageDraw.Draw(canvas)
    
    # Try to load a larger font, fallback to default if not found
    try:
        from PIL import ImageFont
        font_large = ImageFont.truetype("Arial.ttf", 24)
        font_small = ImageFont.truetype("Arial.ttf", 16)
    except:
        try:
            font_large = ImageFont.truetype("/Library/Fonts/Arial.ttf", 24)
            font_small = ImageFont.truetype("/Library/Fonts/Arial.ttf", 16)
        except:
            font_large = None
            font_small = None

    for i, p in enumerate(pantone_options):
        row = i // COLS
        col = i % COLS
        x   = PAD + col * (SWATCH_W + PAD)
        y   = PAD + row * (SWATCH_H + LABEL_H + PAD)

        # Parse hex → RGB
        raw = p.get("hex", "#888888").lstrip("#")
        if len(raw) == 6:
            r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
        else:
            r, g, b = 136, 136, 136

        # Solid color block
        draw.rectangle([x, y, x + SWATCH_W, y + SWATCH_H], fill=(r, g, b))

        # White label area below
        draw.rectangle([x, y + SWATCH_H, x + SWATCH_W, y + SWATCH_H + LABEL_H], fill=(255, 255, 255))

        # Label text
        code = p.get("code", "")
        name = p.get("name", "")
        if font_large:
            draw.text((x + 6, y + SWATCH_H + 6),  code, fill=TEXT_COL, font=font_large)
            draw.text((x + 6, y + SWATCH_H + 32), name, fill=(80, 80, 80), font=font_small)
        else:
            draw.text((x + 6, y + SWATCH_H + 6),  code, fill=TEXT_COL)
            draw.text((x + 6, y + SWATCH_H + 26), name, fill=(80, 80, 80))

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".png", prefix="pantone_swatches_")
        os.close(fd)

    canvas.save(output_path)
    print(f"[render_pantone_swatches] saved {n} swatches → {output_path}")
    return output_path






import json

def map_json(input_json: dict) -> dict:
    # -----------------------------
    # PAGE 4 — Accessories
    # -----------------------------
    accessories = input_json.get("page_4", {}).get("accessories", [])
    for acc in accessories:
        # Build description
        parts = []

        if acc.get("item_description"):
            parts.append(acc["item_description"])
        if acc.get("material"):
            parts.append(acc["material"])
        if acc.get("dimensions"):
            parts.append(acc["dimensions"])

        if parts:
            acc["description"] = " - ".join(parts)

        # Quantity → qty
        if "qty" not in acc and acc.get("quantity") is not None:
            acc["qty"] = acc["quantity"]

        # Placement → position
        if "position" not in acc and acc.get("placement") is not None:
            acc["position"] = acc["placement"]

    # -----------------------------
    # PAGE 5 — Seams
    # -----------------------------
    seams = input_json.get("page_5", {}).get("seams", [])
    for seam in seams:
        if "type" not in seam and seam.get("seam_type") is not None:
            seam["type"] = seam["seam_type"]

        if "symbol" not in seam and seam.get("seam_symbol") is not None:
            seam["symbol"] = seam["seam_symbol"]

        if "allowance" not in seam and seam.get("seam_allowance_mm") is not None:
            seam["allowance"] = seam["seam_allowance_mm"]

        # stitch_density not present → use stitch_size if available
        # if "stich_size" not in seam:
        #     seam["stich_size"] = seam.get("stitch_size")

        if "machine" not in seam and seam.get("machine_type") is not None:
            seam["machine"] = seam["machine_type"]

        # description already exists → keep as-is

    # -----------------------------
    # PAGE 6 — Measurements
    # -----------------------------
    # Now handled directly by Pydantic models.

    print("✅ JSON UPDATED SUCCESSFULLY")
    return input_json


import json
# Top-level debug load removed to prevent import failure when running outside swanky_women directory


from PIL import Image

def combine_images_horizontally(image_paths, output_path):
    """
    image_paths: list of image file paths
    output_path: path to save the combined image
    """

    images = [Image.open(img) for img in image_paths]

    # Get total width and max height
    total_width = sum(img.width for img in images)
    max_height = max(img.height for img in images)

    # Create new blank image
    combined = Image.new("RGB", (total_width, max_height))

    # Paste images one by one
    x_offset = 0
    for img in images:
        combined.paste(img, (x_offset, 0))
        x_offset += img.width

    combined.save(output_path)
    return output_path

# image_paths = ['assets/front.png',"assets/back.png"]
# combine_images_horizontally(image_paths,"final.png")

import os
import numpy as np
from PIL import Image


def remove_left_white_area(img_np, white_threshold=245):
    height, width, _ = img_np.shape
    for x in range(width):
        column = img_np[:, x]
        if not np.all(column >= white_threshold):
            return img_np[:, x:]
    return img_np


def is_mostly_white(grid, white_threshold=245, white_ratio=0.65):
    white_pixels = np.all(grid >= white_threshold, axis=2)
    white_percentage = np.sum(white_pixels) / white_pixels.size
    return white_percentage >= white_ratio


def has_white_on_both_sides(
    grid,
    side_width=20,
    white_threshold=245,
    min_white_ratio=0.10
):
    """
    Keeps grid only if LEFT and RIGHT sides have some white
    """

    # Left side
    left_strip = grid[:, :side_width]
    left_white = np.all(left_strip >= white_threshold, axis=2)
    left_ratio = np.sum(left_white) / left_white.size

    # Right side
    right_strip = grid[:, -side_width:]
    right_white = np.all(right_strip >= white_threshold, axis=2)
    right_ratio = np.sum(right_white) / right_white.size

    return left_ratio >= min_white_ratio and right_ratio >= min_white_ratio


def split_into_grids(
    image_path,
    output_dir,
    grid_height,
    extra_width=190,
    white_threshold=245,
    white_ratio=0.65
):
    os.makedirs(output_dir, exist_ok=True)

    img = Image.open(image_path).convert("RGB")
    img_np = np.array(img)

    img_np = remove_left_white_area(img_np, white_threshold)

    height, width, _ = img_np.shape
    grid_width = grid_height + extra_width
    count = 0

    y_positions = list(range(0, height, grid_height))

    if y_positions[-1] + grid_height > height:
        y_positions[-1] = height - grid_height
    
    final_grid_images = []

    for y in y_positions:
        for x in range(0, width, grid_width):
            if x + grid_width > width:
                continue

            grid = img_np[y:y + grid_height, x:x + grid_width]

            if grid.shape[:2] != (grid_height, grid_width):
                continue

            # Filter 1: mostly white
            if is_mostly_white(grid, white_threshold, white_ratio):
                continue

            # Filter 2: must have white on both left & right
            if not has_white_on_both_sides(grid):
                continue
            
            final_grid_images.append(os.path.join(output_dir, f"grid_{count}.png"))
            Image.fromarray(grid).save(
                os.path.join(output_dir, f"grid_{count}.png")
            )
            count += 1

    print(f"Saved {count} grids after all filters.")
    return final_grid_images




# =========================================================
# AI-ASSISTED DETAIL CROPPING
# =========================================================

def ai_crop_detail_regions(
    images: list,
    garment_details: str,
    output_dir: str = "assets",
    n_crops: int = 4,
    min_crop_size: int = 150,
    white_threshold: float = 0.85,
) -> list:
    """
    Uses Claude Vision to identify the most important detail regions on a garment,
    then crops those exact regions from the source images using PIL.

    Strategy:
    1. Ask Claude Vision to identify top N detail zones with normalized bounding boxes
    2. Crop each zone from the source image
    3. Filter out near-blank crops
    4. Return list of saved crop paths (up to n_crops)

    Falls back to empty list on any error — caller should handle fallback.

    Args:
        images:          list of source image paths (front first)
        garment_details: garment description text to guide what to look for
        output_dir:      where to save cropped images
        n_crops:         how many detail crops to produce
        min_crop_size:   minimum pixel dimension for a valid crop
        white_threshold: fraction of white pixels above which a crop is discarded

    Returns:
        list of saved crop paths
    """
    import json as _json
    import os as _os
    from PIL import Image as PILImage

    # ── Environment Configurations ──
    crop_model = _os.getenv("DETAIL_CROP_MODEL", "google/gemini-3.8-flash")
    frac_min = float(_os.getenv("DETAIL_CROP_SIZE_FRACTION_MIN", "0.55"))
    frac_max = float(_os.getenv("DETAIL_CROP_SIZE_FRACTION_MAX", "0.85"))
    frac_default = float(_os.getenv("DETAIL_CROP_SIZE_FRACTION_DEFAULT", "0.65"))
    min_export_px = int(_os.getenv("DETAIL_CROP_MIN_EXPORT_PX", "600"))

    # ── Step 1: Ask Vision model to identify detail regions ──
    region_prompt = f"""You are an expert fashion technical designer creating close-up construction detail callouts for a production tech pack.

Garment description context:
{garment_details}

Your task: Identify exactly {n_crops} distinct construction detail regions following this STRICT DETAIL PRIORITY HIERARCHY:

1. PRIORITY 1 — TOP STYLE / CUT & NECKLINE:
   Any distinctive architectural cut or styling at the top of the garment: collar construction, lapel notch / peak and gorge seam, curved round neckline, plunge, or neckband styling.

2. PRIORITY 2 — ACCESSORIES, HARDWARE & POCKET TRIMS:
   The primary decorative or functional accessories / hardware: flap pockets, welt pockets, buttons, zipper pulls, belt buckles, or beadwork.
   CRITICAL: If both upper (chest) and lower (waist/hip) pockets exist, treat them as distinct details and crop each one separately!
   NEVER slice through a pocket or button — capture the ENTIRE pocket with breathing room around it.

3. PRIORITY 3 — SLEEVE / CUFF CONSTRUCTION & TRIMS:
   Sleeve cuff with its decorative trim border, cuff vent, buttons, or edge stitching.

4. PRIORITY 4 — CURVED CUTS, SILHOUETTE CONTOURS & HEM:
   Distinctive curved silhouette lines: lower front curved hem corner or peplum curve, contoured waist seams, princess seams, walking slit/vent, or bottom hem finishing.

CRITICAL FRAMING & SIZING RULES:
- GENEROUS, LARGER CROP WINDOW (NO TIGHT CROPS):
  Provide a generous crop window (crop_size_fraction between {frac_min:.2f} and {frac_max:.2f} of image width, recommend ~{frac_default:.2f}) so that the COMPLETE detail is captured with its surrounding construction context.
  NEVER leave parts in half:
  - For pockets: capture the ENTIRE pocket, including the full pocket flap/welt, button, and surrounding panel fabric. Do NOT slice the pocket in half.
  - For lapel & collar: capture the FULL lapel notch, peak, collar roll, and gorge seam down into the chest. Center directly on the fabric of the lapel/notch, NOT on the wearer's neck or throat skin.
  - For button closures: capture the complete button row with surrounding front placket panels.
  - For sleeve cuffs: capture the full width of the cuff, vent, and buttons.
  - For peplum / hems: capture the full sweep of the curved hem and seam.
- AVOID HUMAN BODY PARTS: Center strictly on the garment construction itself (fabric, stitches, collar notch, lapel roll). NEVER center on the model's head, face, lips, chin, or neck skin. For collar/lapel callouts, center on the notch or fold of the fabric on the chest/shoulder area, NOT on the wearer's neck or chin.
- Center the target feature dead in the middle of the frame.

For each detail region, return valid JSON with:
- "label": Short descriptive name of the detail
- "priority_category": One of "top_cut_neckline", "accessories_hardware_pocket", "sleeve_cuff", "curved_hem_contour"
- "reasoning": In-depth technical explanation of WHY this region was chosen, what manufacturing/quality challenges exist here (e.g. trim tension, button placement, puckering, curve radius), and why the factory must inspect it up close.
- "image_index": 0 for front image, 1 for back image
- "center_x": X coordinate of the dead center of the detail as fraction of image width (0.0 to 1.0)
- "center_y": Y coordinate of the dead center of the detail as fraction of image height (0.0 to 1.0)
- "crop_size_fraction": Size of square crop relative to image width ({frac_min:.2f} to {frac_max:.2f}) so the complete detail fits with generous breathing room.

Return ONLY a valid JSON array of exactly {n_crops} objects. No markdown. No code fences. No explanation."""

    try:
        try:
            from llm import analyze_images as _analyze_images
        except ImportError:
            from swanky_women.llm import analyze_images as _analyze_images

        raw, _think = _analyze_images(images, region_prompt, model=crop_model)
        raw = raw.strip()
        # Strip markdown fences
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        regions = _json.loads(raw)
        if not isinstance(regions, list) or len(regions) == 0:
            print("[ai_crop] No valid regions returned from Vision model")
            return []

        print(f"[ai_crop] Vision model ({crop_model}) identified {len(regions)} detail regions")

    except Exception as e:
        print(f"[ai_crop] Vision region detection failed: {e}")
        return []

    # ── Step 2: Crop each region from the source image ──
    saved_crops = []
    _os.makedirs(output_dir, exist_ok=True)

    for i, region in enumerate(regions):
        try:
            img_idx = int(region.get("image_index", 0))
            img_idx = min(img_idx, len(images) - 1)  # clamp to available images
            src_path = images[img_idx]

            img_raw = PILImage.open(src_path)
            # Alpha composite onto white background so background stays clean white
            if img_raw.mode in ("RGBA", "LA") or (img_raw.mode == "P" and "transparency" in img_raw.info):
                img = PILImage.new("RGB", img_raw.size, (255, 255, 255))
                rgba = img_raw.convert("RGBA")
                img.paste(rgba, mask=rgba.split()[3])
            else:
                img = img_raw.convert("RGB")

            W, H = img.size

            # Determine center point and crop size
            if "center_x" in region and "center_y" in region:
                cx = float(region["center_x"]) * W
                cy = float(region["center_y"]) * H
                crop_frac = float(region.get("crop_size_fraction", frac_default))
                crop_frac = max(frac_min, min(frac_max, crop_frac))
                size = max(int(crop_frac * W), int(min(W, H) * 0.35))
            else:
                # Legacy x, y, w, h
                x_val = float(region.get("x", 0.0)) * W
                y_val = float(region.get("y", 0.0)) * H
                w_val = float(region.get("w", 0.50)) * W
                h_val = float(region.get("h", 0.50)) * H
                cx = x_val + w_val / 2.0
                cy = y_val + h_val / 2.0
                size = int(max(w_val, h_val, min(W, H) * 0.35))

            # Enforce true 1:1 square crop centered on (cx, cy)
            half = size / 2.0
            left = int(round(cx - half))
            top = int(round(cy - half))
            right = left + size
            bottom = top + size

            # Handle boundaries by padding with white canvas so target remains centered without shrinking
            if left < 0 or top < 0 or right > W or bottom > H:
                crop_canvas = PILImage.new("RGB", (size, size), (255, 255, 255))
                src_left = max(0, left)
                src_top = max(0, top)
                src_right = min(W, right)
                src_bottom = min(H, bottom)

                paste_x = src_left - left
                paste_y = src_top - top

                sub = img.crop((src_left, src_top, src_right, src_bottom))
                crop_canvas.paste(sub, (paste_x, paste_y))
                crop = crop_canvas
            else:
                crop = img.crop((left, top, right, bottom))

            # Filter near-blank crops
            arr = np.array(crop)
            white_pixels = np.sum(np.all(arr > 240, axis=2))
            total_pixels = arr.shape[0] * arr.shape[1]
            if (white_pixels / total_pixels) > white_threshold:
                print(f"[ai_crop] Region {i} '{region.get('label')}' is mostly white, skipping")
                continue

            # Upscale if below min_export_px using high-fidelity LANCZOS to prevent any blurriness in PDF
            orig_w, orig_h = crop.size
            if crop.width < min_export_px or crop.height < min_export_px:
                scale = max(min_export_px / crop.width, min_export_px / crop.height)
                new_w = int(round(crop.width * scale))
                new_h = int(round(crop.height * scale))
                crop = crop.resize((new_w, new_h), resample=PILImage.Resampling.LANCZOS)

            label_safe = region.get("label", f"detail_{i}").replace(" ", "_").lower()
            crop_path = _os.path.join(output_dir, f"ai_detail_{i}_{label_safe}.png")
            # Save lossless PNG with no compression degradation
            crop.save(crop_path, format="PNG", compress_level=1)
            saved_crops.append(crop_path)
            print(f"[ai_crop] Saved: {crop_path} (orig {orig_w}x{orig_h}px -> export {crop.width}x{crop.height}px) — {region.get('label')}")
            if region.get("reasoning"):
                print(f"         Technical Reasoning: {region.get('reasoning')}")

        except Exception as e:
            print(f"[ai_crop] Failed to crop region {i}: {e}")
            continue

    print(f"[ai_crop] Produced {len(saved_crops)}/{len(regions)} valid detail crops")
    return saved_crops[:n_crops]


def format_technical_sketch(
    sketch_path: str,
    is_two_piece: bool = False,
    output_path: Optional[str] = None
) -> str:
    """
    Ensures technical sketch follows the required horizontal layout:
    - If two-piece (separate upper and bottom wear): creates 4 parts horizontally:
      [Top Front] [Top Back] [Bottom Front] [Bottom Back]
    - If single piece: keeps 2 parts horizontally:
      [Front] [Back]
    """
    from PIL import Image as PILImage
    from typing import Optional
    import numpy as _np
    import os as _os

    if output_path is None:
        output_path = sketch_path

    if not _os.path.exists(sketch_path):
        return sketch_path

    try:
        img = PILImage.open(sketch_path).convert("RGB")
        W, H = img.size

        arr = _np.array(img.convert("L"))
        dark_mask = (arr < 230)
        row_counts = dark_mask.sum(axis=1)

        # Check if vertically stacked (middle 35%-65% has a significant drop in dark pixels)
        mid_start = int(0.35 * H)
        mid_end = int(0.65 * H)
        mid_zone = row_counts[mid_start:mid_end]
        min_idx = _np.argmin(mid_zone)
        min_val = mid_zone[min_idx]
        split_y = mid_start + min_idx

        # Only assume vertically stacked if the gap is very clean (min_val < 5) and the image is very tall
        has_vertical_split = (min_val < 5 and H > W * 1.2)

        if not (is_two_piece or has_vertical_split):
            # Single piece: auto-trim outer white borders
            rows = _np.where(_np.any(dark_mask, axis=1))[0]
            cols = _np.where(_np.any(dark_mask, axis=0))[0]
            if len(rows) > 0 and len(cols) > 0:
                t = max(0, rows[0] - 20)
                b = min(H, rows[-1] + 20)
                l = max(0, cols[0] - 20)
                r = min(W, cols[-1] + 20)
                trimmed = img.crop((l, t, r, b))
                trimmed.save(output_path, quality=95)
            return output_path

        # Two-piece: slice top and bottom segments and place side-by-side horizontally
        top_half = img.crop((0, 0, W, split_y))
        bottom_half = img.crop((0, split_y, W, H))

        def crop_dark(im, pad=10):
            m = (_np.array(im.convert("L")) < 230)
            rows = _np.where(_np.any(m, axis=1))[0]
            cols = _np.where(_np.any(m, axis=0))[0]
            if len(rows) == 0 or len(cols) == 0:
                return im
            return im.crop((
                max(0, cols[0] - pad),
                max(0, rows[0] - pad),
                min(im.width, cols[-1] + pad),
                min(im.height, rows[-1] + pad)
            ))

        t_crop = crop_dark(top_half)
        b_crop = crop_dark(bottom_half)

        target_h = 520
        t_scaled = t_crop.resize((int(round(t_crop.width * (target_h / t_crop.height))), target_h), PILImage.Resampling.LANCZOS)
        b_scaled = b_crop.resize((int(round(b_crop.width * (target_h / b_crop.height))), target_h), PILImage.Resampling.LANCZOS)

        spacing = 60
        total_w = t_scaled.width + spacing + b_scaled.width
        canvas = PILImage.new("RGB", (total_w + 60, target_h + 30), (255, 255, 255))
        canvas.paste(t_scaled, (30, 15))
        canvas.paste(b_scaled, (30 + t_scaled.width + spacing, 15))

        canvas.save(output_path, quality=95)
        print(f"[format_sketch] Converted 2-piece sketch into side-by-side horizontal layout: {output_path} ({canvas.size})")
        return output_path

    except Exception as e:
        print(f"[format_sketch] Error formatting sketch: {e}")
        return sketch_path


# ======================
# Example usage
# ======================
# if __name__ == "__main__":
#     fimage = combine_images_horizontally(["assets/front.png","assets/back.png"],"final.png")
#     print(split_into_grids(image_path=fimage, output_dir="assets", grid_height=1400, extra_width=190))