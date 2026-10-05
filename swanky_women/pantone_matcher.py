#!/usr/bin/env python3
"""
Pantone TCX matcher using pantone.com color finder + Claude Vision verification.

Flow:
1. Takes hex color(s) from garment
2. Scrapes pantone.com/color-finder for TCX options
3. Falls back to local Delta-E if scraper fails
4. Creates a visual swatch grid image with all candidates
5. Returns candidates for Claude Vision to pick best match

Usage:
  python pantone_matcher.py --hex "#F2EEE6" "#2D3D52" --output assets/pantone_grid.png
"""

import os
import sys
import json
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def get_pantone_candidates(hex_color: str) -> list:
    """Get Pantone TCX candidates. Try scraper first, fall back to local Delta-E."""
    hex_clean = hex_color.strip().lstrip('#')

    candidates = []
    source = "unknown"

    # Stage 1: Try pantone.com scraper
    try:
        from pantone_scraper import get_tcx_options
        print(f"  Scraping pantone.com for #{hex_clean}...")
        scraped = get_tcx_options(hex_clean)
        if scraped:
            for opt in scraped:
                code = str(opt.get("code") or opt.get("name", ""))
                if code and "TCX" not in code:
                    code = f"{code} TCX"
                name = opt.get("name", "")
                hex_val = opt.get("hex", "")
                if code:
                    candidates.append({
                        "code": code,
                        "name": name,
                        "hex": hex_val if hex_val else f"#{hex_clean}",
                        "source": "pantone.com"
                    })
            if candidates:
                source = "pantone.com"
                print(f"  ✓ Got {len(candidates)} candidates from pantone.com")
    except Exception as e:
        print(f"  Scraper failed: {str(e)[:80]}")

    # Stage 2: Fall back to local Delta-E
    if not candidates:
        try:
            from utils import nearest_pantone_tcx
            print(f"  Using local Delta-E for #{hex_clean}...")
            results = nearest_pantone_tcx(f"#{hex_clean}", top_k=5)
            for r in results:
                candidates.append({
                    "code": r["code"],
                    "name": r["name"],
                    "hex": r["hex"],
                    "delta_e": r["delta_e"],
                    "source": "local_delta_e"
                })
            source = "local_delta_e"
            print(f"  ✓ Got {len(candidates)} candidates from local Delta-E")
        except Exception as e:
            print(f"  Local Delta-E also failed: {e}")

    return candidates, source


def create_swatch_grid(all_candidates: dict, output_path: str) -> str:
    """Create a visual grid image showing all Pantone candidate swatches.

    all_candidates: {"#F2EEE6": [{"code": "...", "name": "...", "hex": "..."}], ...}
    """
    swatch_w = 120
    swatch_h = 80
    label_h = 50
    padding = 15

    # Calculate grid dimensions
    max_per_row = 5
    total_items = sum(len(v) for v in all_candidates.values())
    rows_needed = 0
    for hex_input, cands in all_candidates.items():
        rows_needed += 1  # header row
        rows_needed += (len(cands) + max_per_row - 1) // max_per_row  # swatch rows

    img_w = max_per_row * (swatch_w + padding) + padding
    img_h = rows_needed * (swatch_h + label_h + padding) + padding * 2
    img_h = max(img_h, 200)

    img = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 11)
        font_header = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    except:
        font = ImageFont.load_default()
        font_header = font

    y = padding

    for hex_input, cands in all_candidates.items():
        # Header: "Input: #F2EEE6"
        draw.text((padding, y), f"Input hex: {hex_input}", fill="black", font=font_header)
        y += 25

        # Draw input color swatch
        hex_clean = hex_input.lstrip('#')
        try:
            r, g, b = int(hex_clean[0:2], 16), int(hex_clean[2:4], 16), int(hex_clean[4:6], 16)
            draw.rectangle([padding, y, padding + swatch_w, y + swatch_h // 2], fill=(r, g, b), outline="black")
        except:
            pass
        y += swatch_h // 2 + 10

        # Draw candidate swatches
        x = padding
        for i, cand in enumerate(cands[:max_per_row * 2]):  # max 10 per input hex
            hex_val = cand.get("hex", "#808080").lstrip('#')
            try:
                r, g, b = int(hex_val[0:2], 16), int(hex_val[2:4], 16), int(hex_val[4:6], 16)
            except:
                r, g, b = 128, 128, 128

            # Swatch rectangle
            draw.rectangle([x, y, x + swatch_w, y + swatch_h], fill=(r, g, b), outline="black")

            # Label below
            code = cand.get("code", "")
            name = cand.get("name", "")
            label = f"{code}\n{name}"
            draw.text((x, y + swatch_h + 2), label, fill="black", font=font)

            x += swatch_w + padding
            if (i + 1) % max_per_row == 0:
                x = padding
                y += swatch_h + label_h + padding

        if len(cands) % max_per_row != 0:
            y += swatch_h + label_h + padding
        y += padding

    img.save(output_path)
    print(f"  ✓ Swatch grid saved: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Match Pantone TCX colors")
    parser.add_argument("--hex", nargs="+", required=True, help="Hex color(s) to match (e.g., '#F2EEE6' '#2D3D52')")
    parser.add_argument("--output", default="assets/pantone_grid.png", help="Output swatch grid image path")
    args = parser.parse_args()

    all_candidates = {}

    for hex_color in args.hex:
        hex_color = hex_color.strip().strip("'\"")
        if not hex_color.startswith('#'):
            hex_color = f"#{hex_color}"

        print(f"\nMatching {hex_color}:")
        candidates, source = get_pantone_candidates(hex_color)
        all_candidates[hex_color] = candidates

        for c in candidates[:5]:
            de = f" ΔE: {c['delta_e']}" if 'delta_e' in c else ""
            print(f"  {c['code']} — {c['name']}{de} [{c.get('source', '')}]")

    # Create visual grid
    grid_path = create_swatch_grid(all_candidates, args.output)

    # Output JSON for skill to parse
    print(f"\n=== CANDIDATES JSON ===")
    print(json.dumps(all_candidates, indent=2))

    return all_candidates


if __name__ == "__main__":
    main()
