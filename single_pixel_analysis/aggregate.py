"""
Combine partial R² JSON files from all workers into a single r2_summary.json.
Run this after the PBS array job finishes.

Usage:
    python aggregate.py
"""

import json
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "single_pixel_results"


def main():
    partials = sorted(RESULTS_DIR.glob("r2_partial_*.json"))
    if not partials:
        print("No r2_partial_*.json files found — nothing to aggregate.")
        return

    print(f"Found {len(partials)} partial files")

    merged = {}
    for p in partials:
        with open(p) as f:
            chunk = json.load(f)
        merged.update(chunk)
        print(f"  {p.name}: {len(chunk)} points")

    # sort north → south, then west → east
    sorted_dict = dict(
        sorted(merged.items(),
               key=lambda kv: (-float(kv[0].split(",")[0]),
                                float(kv[0].split(",")[1])))
    )

    summary_path = RESULTS_DIR / "r2_summary.json"
    with open(summary_path, "w") as f:
        json.dump(sorted_dict, f, indent=2)

    print(f"\nTotal points: {len(sorted_dict)}")
    print(f"Written to:   {summary_path}")


if __name__ == "__main__":
    main()
