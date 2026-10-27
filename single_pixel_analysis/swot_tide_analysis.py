"""
Write per-cycle single-pixel CSV for one coastal point.
No R² here — that is computed by read_pass after the CSV is complete.
"""

import numpy as np
import pandas as pd
from pathlib import Path


def analyze_point(pass_data, ci, cj, pass_number, output_dir):
    """Extract single pixel values across all cycles, write CSV.

    Parameters
    ----------
    pass_data : dict
        Entry from ALL_DATA[pass_number].
    ci, cj : int
        Row / column indices of the pixel.
    pass_number : int
    output_dir : Path

    Returns
    -------
    Path to the written CSV, or None if fewer than 3 usable cycles.
    """
    center_lat = float(pass_data["latitude"][ci, cj])
    center_lon = float(pass_data["longitude"][ci, cj])
    if center_lon > 180:
        center_lon -= 360

    cycles_list = []
    ssh_vals = []
    fes_vals = []
    got_vals = []

    for cycle, cdata in pass_data["cycles"].items():
        ssh_qual = cdata["ssh_karin_2_qual"][ci, cj]
        xover_qual = cdata["height_cor_xover_qual"][ci, cj]
        if ssh_qual != 0 or xover_qual != 0:
            continue

        ssh = cdata["ssh_karin_2"][ci, cj] + cdata["height_cor_xover"][ci, cj]
        fes = cdata["ocean_tide_fes"][ci, cj]
        got = cdata["ocean_tide_got"][ci, cj]

        if np.isnan(ssh) or np.isnan(fes) or np.isnan(got):
            continue

        cycles_list.append(cycle)
        ssh_vals.append(float(ssh))
        fes_vals.append(float(fes))
        got_vals.append(float(got))

    if len(cycles_list) < 3:
        return None

    table = pd.DataFrame({
        "cycle": cycles_list,
        "ssh_karin_2_plus_xover_m": np.array(ssh_vals),
        "ocean_tide_fes_m": np.array(fes_vals),
        "ocean_tide_got_m": np.array(got_vals),
    })

    fname = f"pass_{pass_number:03d}_lat_{center_lat:.4f}_lon_{center_lon:.4f}.csv"
    csv_path = Path(output_dir) / fname
    table.to_csv(csv_path, index=False, float_format="%.6f")
    return csv_path


if __name__ == "__main__":
    print("swot_tide_analysis: library module — import and call analyze_point()")
