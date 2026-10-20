"""
Extract SWOT box-mean time series for a given pass / lat-lon centre,
compute R² of ocean_tide_fes and ocean_tide_got against SSH,
and write a single CSV with those R² values appended.
"""

import argparse
import contextlib
import io
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

BOX_SIZE = 10

REPO_ROOT = Path(__file__).resolve().parents[2]

SSH_LABEL = "ssh_karin_2_plus_xover"
FES_LABEL = "ocean_tide_fes"
GOT_LABEL = "ocean_tide_got"
SSH1_LABEL = "ssh_karin_plus_xover"
FES1_LABEL = "ocean_tide_fes_karin_pixels"
GOT1_LABEL = "ocean_tide_got_karin_pixels"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pass_number", type=int, required=True)
    p.add_argument("--lat", type=float, required=True, help="centre latitude")
    p.add_argument("--lon", type=float, required=True, help="centre longitude")
    p.add_argument("--swot_dir", type=str, default=None,
                   help="override SWOT file directory (default: REPO_ROOT/swot_files_pass_NNN)")
    p.add_argument("-o", "--output", type=str, default=None,
                   help="output CSV path (default: pass_NNN_box_means.csv)")
    return p.parse_args()


def latest_file_per_cycle(swot_dir, pass_number):
    files = {}
    for path in sorted(swot_dir.glob(f"SWOT_L2_LR_SSH_Expert_*_{pass_number:03d}_*.nc")):
        cycle = int(path.name.split("_")[5])
        files[cycle] = path
    return dict(sorted(files.items()))


def box_indices(ds, center_lat, center_lon):
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    lon = np.where(lon > 180, lon - 360, lon)
    dist2 = (lat - center_lat) ** 2 + ((lon - center_lon) * np.cos(np.radians(center_lat))) ** 2
    i, j = np.unravel_index(np.nanargmin(dist2), dist2.shape)
    half = BOX_SIZE // 2
    return slice(i - half, i - half + BOX_SIZE), slice(j - half, j - half + BOX_SIZE)


def load_timeseries(files, center_lat, center_lon):
    cycles, times = [], []
    fields = {label: [] for label in
              (SSH_LABEL, FES_LABEL, GOT_LABEL, SSH1_LABEL, FES1_LABEL, GOT1_LABEL)}
    for cycle, path in files.items():
        with xr.open_dataset(path) as ds:
            rows, cols = box_indices(ds, center_lat, center_lon)
            box = ds.isel(num_lines=rows, num_pixels=cols).load()
        if box.sizes["num_lines"] != BOX_SIZE or box.sizes["num_pixels"] != BOX_SIZE:
            print(f"  [SKIP] cycle {cycle:03d}: box falls off the swath")
            continue
        xover_ok = box["height_cor_xover_qual"].values == 0
        good2 = (box["ssh_karin_2_qual"].values == 0) & xover_ok
        good1 = (box["ssh_karin_qual"].values == 0) & xover_ok
        if not (good2.any() or good1.any()):
            print(f"  [SKIP] cycle {cycle:03d}: no qual = 0 data in box")
            continue
        fes = box["ocean_tide_fes"].values
        got = box["ocean_tide_got"].values
        raw = {
            SSH_LABEL: (box["ssh_karin_2"].values + box["height_cor_xover"].values, good2),
            FES_LABEL: (fes, good2),
            GOT_LABEL: (got, good2),
            SSH1_LABEL: (box["ssh_karin"].values + box["height_cor_xover"].values, good1),
            FES1_LABEL: (fes, good1),
            GOT1_LABEL: (got, good1),
        }
        for label, (vals, good) in raw.items():
            fields[label].append(np.where(good, vals, np.nan))
        cycles.append(cycle)
        times.append(box["time"].values[BOX_SIZE // 2])
        print(f"  [OK] cycle {cycle:03d}")
    fields = {label: np.array(vals) for label, vals in fields.items()}
    return np.array(cycles), np.array(times), fields


def compute_r2(y, x):
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


def build_csv(cycles, times, fields):
    flat = {label: vals.reshape(len(times), -1) for label, vals in fields.items()}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        means = {label: np.nanmean(vals, axis=1) for label, vals in flat.items()}

    r2_fes = compute_r2(means[FES_LABEL], means[SSH_LABEL])
    r2_got = compute_r2(means[GOT_LABEL], means[SSH_LABEL])
    r2_fes_k = compute_r2(means[FES1_LABEL], means[SSH1_LABEL])
    r2_got_k = compute_r2(means[GOT1_LABEL], means[SSH1_LABEL])

    table = pd.DataFrame({
        "cycle": cycles,
        "time_utc": pd.to_datetime(times),
        "n_pixels": np.count_nonzero(~np.isnan(flat[SSH_LABEL]), axis=1),
        "ssh_karin_2_plus_xover_mean_m": means[SSH_LABEL],
        "ocean_tide_fes_mean_m": means[FES_LABEL],
        "ocean_tide_got_mean_m": means[GOT_LABEL],
        "n_pixels_karin": np.count_nonzero(~np.isnan(flat[SSH1_LABEL]), axis=1),
        "ssh_karin_plus_xover_mean_m": means[SSH1_LABEL],
        "ocean_tide_fes_karin_pixels_mean_m": means[FES1_LABEL],
        "ocean_tide_got_karin_pixels_mean_m": means[GOT1_LABEL],
        "r2_fes_vs_ssh_karin_2": r2_fes,
        "r2_got_vs_ssh_karin_2": r2_got,
        "r2_fes_vs_ssh_karin": r2_fes_k,
        "r2_got_vs_ssh_karin": r2_got_k,
    })
    return table, {"fes_k2": r2_fes, "got_k2": r2_got,
                    "fes_k": r2_fes_k, "got_k": r2_got_k}


if __name__ == "__main__":
    args = parse_args()
    swot_dir = Path(args.swot_dir) if args.swot_dir else REPO_ROOT / f"swot_files_pass_{args.pass_number:03d}"
    out_csv = Path(args.output) if args.output else Path(f"pass_{args.pass_number:03d}_box_means.csv")

    files = latest_file_per_cycle(swot_dir, args.pass_number)
    print(f"Found {len(files)} cycles for pass {args.pass_number}")

    cycles, times, fields = load_timeseries(files, args.lat, args.lon)
    if len(cycles) == 0:
        print("No valid cycles found — nothing to write.")
        raise SystemExit(1)

    table, r2s = build_csv(cycles, times, fields)
    table.to_csv(out_csv, index=False, float_format="%.4f")

    print(f"\nR² ocean_tide_fes vs ssh_karin_2: {r2s['fes_k2']:.4f}")
    print(f"R² ocean_tide_got vs ssh_karin_2: {r2s['got_k2']:.4f}")
    print(f"R² ocean_tide_fes vs ssh_karin:   {r2s['fes_k']:.4f}")
    print(f"R² ocean_tide_got vs ssh_karin:   {r2s['got_k']:.4f}")
    print(f"\nWrote {out_csv}")
