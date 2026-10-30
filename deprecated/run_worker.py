"""
Parallel worker: processes a subset of passes.
Called by the PBS array job — each array element handles a different slice.

Usage:
    python run_worker.py --worker-id 1 --total-workers 32
"""

import argparse
import json
import sys
import time
from pathlib import Path

# parent directory contains setup.py and read_pass.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from setup import FILE_INDEX, load_passes
from read_pass import process_pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-id", type=int, required=True,
                        help="1-based worker index (PBS_ARRAY_INDEX)")
    parser.add_argument("--total-workers", type=int, required=True,
                        help="total number of workers in the array job")
    args = parser.parse_args()

    wid = args.worker_id
    n_workers = args.total_workers

    all_passes = sorted(FILE_INDEX.keys())
    my_passes = [p for i, p in enumerate(all_passes)
                 if i % n_workers == (wid - 1)]

    print(f"Worker {wid}/{n_workers}: assigned {len(my_passes)} passes",
          flush=True)
    if not my_passes:
        print("Nothing to do — exiting.")
        return

    PROJECT_DIR = Path(__file__).resolve().parent.parent
    RESULTS_DIR = PROJECT_DIR / "tide_analysis_results"
    RESULTS_DIR.mkdir(exist_ok=True)

    data = load_passes(my_passes)

    r2_dict = {}
    t0 = time.time()

    for idx, pass_num in enumerate(my_passes, 1):
        if pass_num not in data:
            continue
        print(f"  [{idx}/{len(my_passes)}] Pass {pass_num:03d} ...",
              end=" ", flush=True)

        results = process_pass(pass_num, data[pass_num], RESULTS_DIR)

        for r in results:
            key = f"{r['lat']:.4f},{r['lon']:.4f}"
            r2_dict[key] = [r["r2_fes"], r["r2_got"], r["fes_var"], r["got_var"]]

        elapsed = time.time() - t0
        print(f"{len(results)} points – {elapsed / 60:.1f} min elapsed",
              flush=True)

    partial_path = RESULTS_DIR / f"r2_partial_{wid:03d}.json"
    with open(partial_path, "w") as f:
        json.dump(r2_dict, f, indent=2)

    print(f"\nWorker {wid} done: {len(r2_dict)} points → {partial_path}")


if __name__ == "__main__":
    main()
