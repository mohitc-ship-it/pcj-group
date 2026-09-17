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
        if lab.lab_l < 30:  # remove deep shadows
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

with open("data/master_filled.json","r",encoding="utf-8") as f:
    json_r = json.load(f)

# print(map_json(json_r))


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

    # ── Step 1: Ask Claude Vision to identify detail regions ──
    region_prompt = f"""You are a fashion technical designer analyzing garment photographs for a tech pack.

Your task: Identify the {n_crops} most important DETAIL REGIONS on this garment that a manufacturer needs to see up close.

Focus on:
- Closures (buttons, zippers, hooks, snaps)
- Collar / neckline construction
- Sleeve / cuff details  
- Hem / bottom edge finishing
- Seam intersections, pockets, pleats, ruching, gathering
- Any distinctive construction feature visible

Garment description context:
{garment_details}

For each detail region, return:
- "label": short name (e.g. "Collar", "Front Zipper", "Hem Detail")
- "description": one sentence on why this detail matters for manufacturing
- "image_index": which image to crop from (0 = first/front image, 1 = second/back image, etc.)
- "x": left edge as fraction of image width (0.0–1.0)
- "y": top edge as fraction of image height (0.0–1.0)
- "w": width as fraction of image width (0.05–0.6)
- "h": height as fraction of image height (0.05–0.6)

Rules:
- Coordinates must be inside the image (x+w <= 1.0, y+h <= 1.0)
- Each crop must be at least 5% of image in both dimensions
- Only label regions that are CLEARLY VISIBLE in the images
- Prioritize regions that show construction methods a factory needs

Return ONLY valid JSON — a list of exactly {n_crops} objects. No markdown. No explanation.
Example:
[
  {{"label": "Collar", "description": "Stand collar with visible topstitching", "image_index": 0, "x": 0.3, "y": 0.05, "w": 0.4, "h": 0.2}},
  {{"label": "Front Closure", "description": "Button placket with 5 buttons", "image_index": 0, "x": 0.4, "y": 0.2, "w": 0.2, "h": 0.5}}
]
"""

    try:
        from llm import analyze_images as _analyze_images

        raw, _think = _analyze_images(images, region_prompt)
        raw = raw.strip()
        # Strip markdown fences
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        regions = _json.loads(raw)
        if not isinstance(regions, list) or len(regions) == 0:
            print("[ai_crop] No valid regions returned from Claude Vision")
            return []

        print(f"[ai_crop] Claude identified {len(regions)} detail regions")

    except Exception as e:
        print(f"[ai_crop] Claude Vision region detection failed: {e}")
        return []

    # ── Step 2: Crop each region from the source image ──
    saved_crops = []
    _os.makedirs(output_dir, exist_ok=True)

    for i, region in enumerate(regions):
        try:
            img_idx = int(region.get("image_index", 0))
            img_idx = min(img_idx, len(images) - 1)  # clamp to available images
            src_path = images[img_idx]

            img = PILImage.open(src_path).convert("RGB")
            W, H = img.size

            # Convert normalized coords to pixels
            x = float(region.get("x", 0.0))
            y = float(region.get("y", 0.0))
            w = float(region.get("w", 0.3))
            h = float(region.get("h", 0.3))

            # Clamp to image bounds
            x = max(0.0, min(x, 1.0))
            y = max(0.0, min(y, 1.0))
            w = max(0.05, min(w, 1.0 - x))
            h = max(0.05, min(h, 1.0 - y))

            left   = int(x * W)
            top    = int(y * H)
            right  = int((x + w) * W)
            bottom = int((y + h) * H)

            # Skip crops that are too small
            if (right - left) < min_crop_size or (bottom - top) < min_crop_size:
                print(f"[ai_crop] Region {i} '{region.get('label')}' too small, skipping")
                continue

            crop = img.crop((left, top, right, bottom))

            # Filter near-blank crops
            arr = np.array(crop)
            white_pixels = np.sum(np.all(arr > 240, axis=2))
            total_pixels = arr.shape[0] * arr.shape[1]
            if (white_pixels / total_pixels) > white_threshold:
                print(f"[ai_crop] Region {i} '{region.get('label')}' is mostly white, skipping")
                continue

            label_safe = region.get("label", f"detail_{i}").replace(" ", "_").lower()
            crop_path = _os.path.join(output_dir, f"ai_detail_{i}_{label_safe}.png")
            crop.save(crop_path)
            saved_crops.append(crop_path)
            print(f"[ai_crop] Saved: {crop_path} ({right-left}x{bottom-top}px) — {region.get('label')}")

        except Exception as e:
            print(f"[ai_crop] Failed to crop region {i}: {e}")
            continue

    print(f"[ai_crop] Produced {len(saved_crops)}/{len(regions)} valid detail crops")
    return saved_crops[:n_crops]


# ======================
# Example usage
# ======================
# if __name__ == "__main__":
#     fimage = combine_images_horizontally(["assets/front.png","assets/back.png"],"final.png")
#     print(split_into_grids(image_path=fimage, output_dir="assets", grid_height=1400, extra_width=190))