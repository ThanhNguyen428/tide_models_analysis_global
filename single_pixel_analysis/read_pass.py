"""
Steps 2–4 from single_pixel_logic.txt, plus R² and variance from CSVs.

    2. Identify coastline per pass
    3. Check every coastal point with valid quality
    4. For qualifying points: write per-cycle CSV, then compute R² and variance
"""

import numpy as np
import pandas as pd
from pathlib import Path

from setup import (
    COAST_DIST_MAX,
    DEPTH_COASTAL_MAX,
    DEPTH_SHALLOW_LIMIT,
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


def compute_metrics_from_csv(csv_path):
    """Read a per-point CSV and return (r2_fes, r2_got, fes_var, got_var).

    Returns None if any cycle has dynamic_ice_flag != 0.
    """
    df = pd.read_csv(csv_path)

    if (df["dynamic_ice_flag"] != 0).any():
        return None

    ssh = df["ssh_karin_2_plus_xover_m"].values
    fes = df["ocean_tide_fes_m"].values
    got = df["ocean_tide_got_m"].values
    return (
        compute_r2(fes, ssh),
        compute_r2(got, ssh),
        np.var(ssh, ddof=1),
        np.var(fes, ddof=1),
        np.var(got, ddof=1)
    )


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


# ── steps 3 & 4 ────────────────────────────────────────────────────────────

def process_pass(pass_number, pass_data, output_dir):
    """Full pipeline for one pass — single pixel analysis.

    For each qualifying coastal pixel:
      1. swot_tide_analysis writes the per-cycle CSV (no R²)
      2. this function reads it back and computes R² and correlated variance

    Returns list of dicts: {lat, lon, r2_fes, r2_got, ssh_var, fes_var, got_var}
    """
    depth = pass_data["depth_or_elevation"]
    n_lines, n_pixels = depth.shape

    coast_mask = identify_coastline(pass_data)

    results = []

    for i in range(n_lines):
        for j in range(n_pixels):
            if not coast_mask[i, j]:
                continue
            if depth[i, j] < DEPTH_SHALLOW_LIMIT:
                continue

            csv_path = analyze_point(
                pass_data, i, j, pass_number, output_dir,
            )
            if csv_path is None:
                continue

            metrics = compute_metrics_from_csv(csv_path)
            if metrics is None:
                continue
            r2_fes, r2_got, ssh_var, fes_var, got_var = metrics

            center_lat = float(pass_data["latitude"][i, j])
            center_lon = float(pass_data["longitude"][i, j])
            if center_lon > 180:
                center_lon -= 360

            results.append({
                "lat": center_lat,
                "lon": center_lon,
                "r2_fes": float(r2_fes),
                "r2_got": float(r2_got),
                "ssh_var": float(ssh_var),
                "fes_var": float(fes_var),
                "got_var": float(got_var),
            })

    return results


if __name__ == "__main__":
    print("read_pass: library module — import and call process_pass()")
