"""
Write per-cycle box-mean CSV for a single coastal point.
No R² here — that is computed by read_pass after the CSV is complete.
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from setup import PATCH_SIZE


def analyze_point(pass_data, ci, cj, ocean_mask, pass_number, output_dir):
    """Extract 10×10 patch across all cycles, write CSV with box means.

    Parameters
    ----------
    pass_data : dict
        Entry from ALL_DATA[pass_number].
    ci, cj : int
        Center row / column indices in the pass arrays.
    ocean_mask : ndarray, bool, shape (PATCH_SIZE, PATCH_SIZE)
        Valid ocean pixels inside the patch (depth in [-50, 0]).
    pass_number : int
    output_dir : Path

    Returns
    -------
    Path to the written CSV, or None if fewer than 3 usable cycles.
    """
    half = PATCH_SIZE // 2
    row_sl = slice(ci - half, ci + half)
    col_sl = slice(cj - half, cj + half)

    center_lat = float(pass_data["latitude"][ci, cj])
    center_lon = float(pass_data["longitude"][ci, cj])
    if center_lon > 180:
        center_lon -= 360

    cycles_list = []
    ssh_means = []
    fes_means = []
    got_means = []
    n_pixels_list = []

    for cycle, cdata in pass_data["cycles"].items():
        ssh_patch = (cdata["ssh_karin_2"][row_sl, col_sl]
                     + cdata["height_cor_xover"][row_sl, col_sl])
        fes_patch = cdata["ocean_tide_fes"][row_sl, col_sl]
        got_patch = cdata["ocean_tide_got"][row_sl, col_sl]

        qual = ((cdata["ssh_karin_2_qual"][row_sl, col_sl] == 0)
                & (cdata["height_cor_xover_qual"][row_sl, col_sl] == 0))
        good = ocean_mask & qual

        if not good.any():
            continue

        ssh_vals = np.where(good, ssh_patch, np.nan)
        fes_vals = np.where(good, fes_patch, np.nan)
        got_vals = np.where(good, got_patch, np.nan)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            ssh_means.append(np.nanmean(ssh_vals))
            fes_means.append(np.nanmean(fes_vals))
            got_means.append(np.nanmean(got_vals))

        n_pixels_list.append(int(good.sum()))
        cycles_list.append(cycle)

    if len(cycles_list) < 3:
        return None

    table = pd.DataFrame({
        "cycle": cycles_list,
        "n_pixels": n_pixels_list,
        "ssh_karin_2_plus_xover_mean_m": np.array(ssh_means),
        "ocean_tide_fes_mean_m": np.array(fes_means),
        "ocean_tide_got_mean_m": np.array(got_means),
    })

    fname = f"pass_{pass_number:03d}_lat_{center_lat:.4f}_lon_{center_lon:.4f}.csv"
    csv_path = Path(output_dir) / fname
    table.to_csv(csv_path, index=False, float_format="%.6f")
    return csv_path


if __name__ == "__main__":
    print("swot_tide_analysis: library module — import and call analyze_point()")
