"""
Single-node sequential driver: processes every pass in FILE_INDEX in order.

The parallel counterpart is NAS_scripts/run_worker_single_pixel.py, which
splits the same work across a PBS array job.

Usage:
    python run_sequential.py
"""

import json
import time
from pathlib import Path

from setup import load_passes
from read_pass import process_pass


def main():
    RESULTS_DIR = Path(__file__).resolve().parent.parent / "single_pixel_results"
    RESULTS_DIR.mkdir(exist_ok=True)

    all_data = load_passes()

    r2_dict = {}
    total_passes = len(all_data)
    t0 = time.time()

    for idx, (pass_num, pass_data) in enumerate(all_data.items(), 1):
        print(f"[{idx}/{total_passes}] Pass {pass_num:03d} ...",
              end=" ", flush=True)

        results = process_pass(pass_num, pass_data, RESULTS_DIR)

        for r in results:
            key = f"{r['lat']:.4f},{r['lon']:.4f}"
            r2_dict[key] = [r["r2_fes"], r["r2_got"],
                            r["ssh_std"], r["fes_std"], r["got_std"]]

        elapsed = time.time() - t0
        print(f"{len(results)} points – {elapsed / 60:.1f} min elapsed",
              flush=True)

    # sort north → south, then west → east
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


if __name__ == "__main__":
    main()
