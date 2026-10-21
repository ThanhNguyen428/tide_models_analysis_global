"""
Steps 2–5 from general_logic.txt, plus R² computation from finished CSVs.

    2. Identify coastline per pass
    3. Segment coastline into 20 km chunks
    4. Check every non-NaN coastal point in each segment
    5. For qualifying points: write per-cycle CSV, then compute R² from it
"""

import numpy as np
import pandas as pd
from pathlib import Path

from setup import (
    COAST_DIST_MAX,
    DEPTH_COASTAL_MAX,
    DEPTH_SHALLOW_LIMIT,
    PATCH_SIZE,
    OCEAN_FRAC_MIN,
    SEGMENT_KM,
    ALONG_TRACK_KM,
)
from swot_tide_analysis import analyze_point


# ── R² ─────────────────────────────────────────────────────────────────────

def compute_r2(y, x):
    """R² via OLS regression. Returns NaN if fewer than 3 valid points."""
    valid = ~(np.isnan(y) | np.isnan(x))
    if valid.sum() < 3:
        return np.nan
    y, x = y[valid], x[valid]
    design = np.column_stack([np.ones_like(x), x])
    (b0, b1), *_ = np.linalg.lstsq(design, y, rcond=None)
    rss = np.sum((y - (b0 + b1 * x)) ** 2)
    tss = np.sum((y - y.mean()) ** 2)
    if tss == 0:
        return np.nan
    return 1 - rss / tss


def compute_r2_from_csv(csv_path):
    """Read a per-point CSV written by swot_tide_analysis and return (r2_fes, r2_got)."""
    df = pd.read_csv(csv_path)
    ssh = df["ssh_karin_2_plus_xover_mean_m"].values
    fes = df["ocean_tide_fes_mean_m"].values
    got = df["ocean_tide_got_mean_m"].values
    return compute_r2(fes, ssh), compute_r2(got, ssh)


# ── step 2 ──────────────────────────────────────────────────────────────────

def identify_coastline(pass_data):
    """Coastline mask: distance_to_coast in [0, 5000] AND depth_or_elevation <= 0."""
    dtc = pass_data["distance_to_coast"]
    depth = pass_data["depth_or_elevation"]
    return (
        (dtc >= 0) & (dtc <= COAST_DIST_MAX)
        & (depth <= DEPTH_COASTAL_MAX)
        & ~np.isnan(dtc) & ~np.isnan(depth)
    )


# ── step 3 ──────────────────────────────────────────────────────────────────

def segment_coastline(coast_mask):
    """Divide rows with coastal pixels into ~20 km along-track segments."""
    rows_with_coast = np.where(coast_mask.any(axis=1))[0]
    if len(rows_with_coast) == 0:
        return []
    rows_per_seg = max(1, round(SEGMENT_KM / ALONG_TRACK_KM))
    segments = []
    for i in range(0, len(rows_with_coast), rows_per_seg):
        segments.append(rows_with_coast[i : i + rows_per_seg])
    return segments


# ── steps 4 & 5 ────────────────────────────────────────────────────────────

def process_pass(pass_number, pass_data, output_dir):
    """Full pipeline for one pass.

    For each qualifying coastal point:
      1. swot_tide_analysis writes the per-cycle CSV  (no R²)
      2. this function reads it back and computes R²

    Returns list of dicts: {lat, lon, r2_fes, r2_got}
    """
    depth = pass_data["depth_or_elevation"]
    n_lines, n_pixels = depth.shape
    half = PATCH_SIZE // 2

    coast_mask = identify_coastline(pass_data)
    segments = segment_coastline(coast_mask)
    if not segments:
        return []

    results = []

    for seg_rows in segments:
        for i in seg_rows:
            for j in range(n_pixels):
                if not coast_mask[i, j]:
                    continue
                if depth[i, j] < DEPTH_SHALLOW_LIMIT:
                    continue
                if (i < half or i + half > n_lines
                        or j < half or j + half > n_pixels):
                    continue

                patch_depth = depth[i - half:i + half, j - half:j + half]

                # ocean = valid (not NaN) and at or below sea level
                ocean_mask = (patch_depth <= 0) & ~np.isnan(patch_depth)

                # keep patch only if >= 1/3 of pixels are ocean
                if ocean_mask.sum() < OCEAN_FRAC_MIN * PATCH_SIZE * PATCH_SIZE:
                    continue

                # step 5a: write per-cycle CSV
                csv_path = analyze_point(
                    pass_data, i, j, ocean_mask, pass_number, output_dir,
                )
                if csv_path is None:
                    continue

                # step 5b: compute R² from the finished CSV
                r2_fes, r2_got = compute_r2_from_csv(csv_path)

                center_lat = float(pass_data["latitude"][i, j])
                center_lon = float(pass_data["longitude"][i, j])
                if center_lon > 180:
                    center_lon -= 360

                results.append({
                    "lat": center_lat,
                    "lon": center_lon,
                    "r2_fes": float(r2_fes),
                    "r2_got": float(r2_got),
                })

    return results


if __name__ == "__main__":
    print("read_pass: library module — import and call process_pass()")
