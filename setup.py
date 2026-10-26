import sys
import time
import numpy as np
import xarray as xr
from pathlib import Path

# ── paths ──
SWOT_MIRROR = Path("/nobackupp29/nmccurdy/swot_mirror/SWOT_L2_LR_SSH_D")

# ── thresholds / constants (from general_logic.txt) ──
LAT_BOUNDS = (-25, 25)
COAST_DIST_MAX = 5000          # metres – distance_to_coast <= this
DEPTH_COASTAL_MAX = 0          # depth_or_elevation <= 0 for coastline mask
DEPTH_SHALLOW_LIMIT = -50      # only process points shallower than -50 m
PATCH_SIZE = 5                # 5x5 pixel patch
OCEAN_FRAC_MIN = 1 / 4         # patch must be >= 1/4 ocean

# variables that are the same across every cycle of a pass (grid properties)
STATIC_VARS = ["latitude", "longitude", "distance_to_coast", "depth_or_elevation"]

# variables that change per cycle (measurements)
CYCLE_VARS = [
    "ssh_karin_2", "height_cor_xover",
    "ocean_tide_fes", "ocean_tide_got",
    "ssh_karin_2_qual", "height_cor_xover_qual",
]


def _build_file_index():
    """Scan SWOT_MIRROR → {pass_number: {cycle: Path}} for all Expert files."""
    index = {}
    for cycle_dir in sorted(SWOT_MIRROR.iterdir()):
        if not cycle_dir.is_dir():
            continue
        for nc in cycle_dir.glob("SWOT_L2_LR_SSH_Expert_*.nc"):
            parts = nc.name.split("_")
            cycle = int(parts[5])
            pass_num = int(parts[6])
            index.setdefault(pass_num, {})[cycle] = nc
    for pass_num in index:
        index[pass_num] = dict(sorted(index[pass_num].items()))
    return dict(sorted(index.items()))


# built at import time (fast — just scans filenames)
FILE_INDEX = _build_file_index()


def load_passes(pass_numbers=None):
    """Load SWOT Expert files into memory, subset to LAT_BOUNDS.

    Parameters
    ----------
    pass_numbers : list of int, optional
        Which passes to load.  None → all passes in FILE_INDEX.

    Returns
    -------
    dict : {pass_number: {"latitude", "longitude", ..., "cycles": {cycle: {...}}}}
    """
    if pass_numbers is None:
        pass_numbers = sorted(FILE_INDEX.keys())

    to_load = {p: FILE_INDEX[p] for p in pass_numbers if p in FILE_INDEX}
    total_files = sum(len(v) for v in to_load.values())
    print(f"Loading {total_files} files for {len(to_load)} passes "
          f"(lat {LAT_BOUNDS[0]} to {LAT_BOUNDS[1]}) ...")
    sys.stdout.flush()

    all_data = {}
    files_done = 0
    t0 = time.time()

    for pass_num, cycle_paths in to_load.items():
        pass_data = {"cycles": {}}
        row_indices = None
        n_rows = None          # consistent row count across all cycles

        for cycle, path in cycle_paths.items():
            with xr.open_dataset(path) as ds:
                n_lines = ds.dims["num_lines"]

                if row_indices is None:
                    lat = ds["latitude"].values
                    band = np.any(
                        (lat >= LAT_BOUNDS[0]) & (lat <= LAT_BOUNDS[1]),
                        axis=1,
                    )
                    row_indices = np.where(band)[0]
                    if len(row_indices) == 0:
                        files_done += len(cycle_paths)
                        break

                # clip indices to this cycle's actual size
                idx = row_indices[row_indices < n_lines]

                if n_rows is None:
                    n_rows = len(idx)
                    subset = ds.isel(num_lines=idx)
                    for var in STATIC_VARS:
                        pass_data[var] = subset[var].values.astype(np.float32)
                else:
                    # keep the minimum common row count
                    if len(idx) < n_rows:
                        n_rows = len(idx)
                        for var in STATIC_VARS:
                            pass_data[var] = pass_data[var][:n_rows]
                        for prev in pass_data["cycles"].values():
                            for var in CYCLE_VARS:
                                prev[var] = prev[var][:n_rows]

                subset = ds.isel(num_lines=idx[:n_rows])
                cycle_dict = {}
                for var in CYCLE_VARS:
                    cycle_dict[var] = subset[var].values.astype(np.float32)
                pass_data["cycles"][cycle] = cycle_dict

            files_done += 1
            if files_done % 200 == 0:
                elapsed = time.time() - t0
                rate = files_done / elapsed
                eta = (total_files - files_done) / rate / 60
                print(f"  {files_done}/{total_files} files "
                      f"({files_done/total_files*100:.0f}%) "
                      f"– {rate:.0f} files/s – ETA {eta:.0f} min",
                      flush=True)

        if pass_data.get("cycles"):
            all_data[pass_num] = pass_data

    elapsed = time.time() - t0
    print(f"Done: {len(all_data)} passes loaded in {elapsed/60:.1f} min",
          flush=True)
    return all_data


if __name__ == "__main__":
    # ── single-node sequential fallback ──
    sys.modules["setup"] = sys.modules[__name__]

    import json
    from read_pass import process_pass

    RESULTS_DIR = Path("tide_analysis_results")
    RESULTS_DIR.mkdir(exist_ok=True)

    ALL_DATA = load_passes()

    r2_dict = {}
    total_passes = len(ALL_DATA)
    t0 = time.time()

    for idx, (pass_num, pass_data) in enumerate(ALL_DATA.items(), 1):
        print(f"[{idx}/{total_passes}] Pass {pass_num:03d} ...",
              end=" ", flush=True)

        results = process_pass(pass_num, pass_data, RESULTS_DIR)

        for r in results:
            key = f"{r['lat']:.4f},{r['lon']:.4f}"
            r2_dict[key] = [r["r2_fes"], r["r2_got"], r["fes_var"], r["got_var"]]

        elapsed = time.time() - t0
        print(f"{len(results)} points – {elapsed / 60:.1f} min elapsed",
              flush=True)

    sorted_dict = dict(
        sorted(r2_dict.items(),
               key=lambda kv: (-float(kv[0].split(",")[0]),
                                float(kv[0].split(",")[1])))
    )

    summary_path = RESULTS_DIR / "r2_summary.json"
    with open(summary_path, "w") as f:
        json.dump(sorted_dict, f, indent=2)

    print(f"\nDone: {len(sorted_dict)} total points")
    print(f"CSVs in:   {RESULTS_DIR}/")
    print(f"Summary:   {summary_path}")
