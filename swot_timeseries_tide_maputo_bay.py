import warnings
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


PASS_NUMBER = 165
CENTER_LAT = -26.02
CENTER_LON = 32.76
BOX_SIZE = 10

REPO_ROOT = Path(__file__).resolve().parents[2]
SWOT_DIR = REPO_ROOT / f"swot_files_pass_{PASS_NUMBER:03d}"
SSH_OUT_DIR = Path(__file__).resolve().parent / "timeseries_ssh_plots_maputo_bay"
TIDE_OUT_DIR = Path(__file__).resolve().parent / "timeseries_tide_plots_maputo_bay"
BOX_MEAN_CSV = Path(__file__).resolve().parent / f"pass_{PASS_NUMBER:03d}_maputo_box_means.csv"

SSH_LABEL = "ssh_karin_2 + height_cor_xover (m)"
FES_LABEL = "ocean_tide_fes (m)"
GOT_LABEL = "ocean_tide_got (m)"

# same fields under the ssh_karin quality flag instead of ssh_karin_2
SSH1_LABEL = "ssh_karin + height_cor_xover (m)"
FES1_LABEL = "ocean_tide_fes (m) [ssh_karin pixels]"
GOT1_LABEL = "ocean_tide_got (m) [ssh_karin pixels]"


def latest_file_per_cycle():
    """Map cycle number -> newest product version (e.g. _02 over _01)."""
    files = {}
    for path in sorted(SWOT_DIR.glob(f"SWOT_L2_LR_SSH_Expert_*_{PASS_NUMBER:03d}_*.nc")):
        cycle = int(path.name.split("_")[5])
        files[cycle] = path  # sorted, so the last one wins
    return dict(sorted(files.items()))


def box_indices(ds):
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    lon = np.where(lon > 180, lon - 360, lon)
    dist2 = (lat - CENTER_LAT) ** 2 + ((lon - CENTER_LON) * np.cos(np.radians(CENTER_LAT))) ** 2
    i, j = np.unravel_index(np.nanargmin(dist2), dist2.shape)
    half = BOX_SIZE // 2
    return slice(i - half, i - half + BOX_SIZE), slice(j - half, j - half + BOX_SIZE)


def load_timeseries(files):
    """Return cycles, times, {label: (cycle, row, col) array}, lat, lon.

    Each SSH variant and its tide fields are NaN wherever height_cor_xover_qual or
    the matching SSH quality flag (ssh_karin_2_qual, or ssh_karin_qual for the
    *_LABEL fields tagged [ssh_karin pixels]) is set.
    """
    cycles, times = [], []
    fields = {label: [] for label in
              (SSH_LABEL, FES_LABEL, GOT_LABEL, SSH1_LABEL, FES1_LABEL, GOT1_LABEL)}
    box_lat = box_lon = None
    for cycle, path in files.items():
        with xr.open_dataset(path) as ds:
            rows, cols = box_indices(ds)
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
        if box_lat is None:
            box_lat = box["latitude"].values
            box_lon = box["longitude"].values
        print(f"  [OK] cycle {cycle:03d}")
    fields = {label: np.array(vals) for label, vals in fields.items()}
    return np.array(cycles), np.array(times), fields, box_lat, box_lon


def write_box_mean_csv(cycles, times, fields, path):
    """One row per cycle: box means (qual = 0 pixels only) of SSH, FES and GOT."""
    flat = {label: vals.reshape(len(times), -1) for label, vals in fields.items()}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN cycles
        means = {label: np.nanmean(vals, axis=1) for label, vals in flat.items()}
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
    })
    table.to_csv(path, index=False, float_format="%.4f")


def format_time_axis(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.tick_params(axis="x", rotation=30)
    ax.grid(alpha=0.3)


def plot_pixel(times, panels, lat, lon, row, col, out_dir):
    """panels: list of (label, series) drawn top to bottom."""
    fig, axes = plt.subplots(len(panels), 1, figsize=(10, 4.5 * len(panels)),
                             sharex=True, squeeze=False, constrained_layout=True)
    for ax, (label, series) in zip(axes[:, 0], panels):
        valid = ~np.isnan(series)
        ax.plot(times[valid], series[valid], "o-", color="tab:blue", markersize=4.5, linewidth=0.8)
        ax.set_ylabel(label)
        format_time_axis(ax)
    n_valid = np.count_nonzero(~np.isnan(panels[0][1]))
    axes[0, 0].set_title(
        f"Pass {PASS_NUMBER} pixel (row {row}, col {col}) at "
        f"{lat:.4f}°, {lon:.4f}°  —  {n_valid} cycles with qual = 0",
        fontsize=10,
    )
    out_path = out_dir / f"pass_{PASS_NUMBER:03d}_pixel_r{row}_c{col}.png"
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def plot_overview(times, panels, box_lat, box_lon, out_dir):
    """panels: list of (label, (cycle, row, col) array) drawn top to bottom."""
    fig, axes = plt.subplots(len(panels), 1, figsize=(11, 5 * len(panels)),
                             sharex=True, squeeze=False, constrained_layout=True)
    for ax, (label, values) in zip(axes[:, 0], panels):
        flat = values.reshape(len(times), -1)
        for k in range(flat.shape[1]):
            valid = ~np.isnan(flat[:, k])
            ax.plot(times[valid], flat[valid, k], color="0.8", linewidth=0.5, zorder=1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN cycles
            box_mean = np.nanmean(flat, axis=1)
        valid = ~np.isnan(box_mean)
        ax.plot(times[valid], box_mean[valid], "o-", color="tab:blue", markersize=4, label="box mean")
        ax.set_ylabel(label)
        format_time_axis(ax)
        ax.legend(fontsize=8)
    axes[0, 0].set_title(
        f"Pass {PASS_NUMBER}, {BOX_SIZE}x{BOX_SIZE} pixels around "
        f"{CENTER_LAT:.4f}°, {CENTER_LON:.4f}° "
        f"(lat {np.nanmin(box_lat):.3f}–{np.nanmax(box_lat):.3f}, "
        f"lon {np.nanmin(box_lon):.3f}–{np.nanmax(box_lon):.3f})  —  qual = 0 only, "
        f"{valid.sum()} cycles",
        fontsize=10,
    )
    fig.savefig(out_dir / f"pass_{PASS_NUMBER:03d}_box_overview.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    files = latest_file_per_cycle()
    print(f"Found {len(files)} cycles for pass {PASS_NUMBER}")

    cycles, times, fields, box_lat, box_lon = load_timeseries(files)
    write_box_mean_csv(cycles, times, fields, BOX_MEAN_CSV)
    print(f"Wrote {BOX_MEAN_CSV}")

    outputs = {
        SSH_OUT_DIR: [SSH_LABEL, SSH1_LABEL],
        TIDE_OUT_DIR: [FES_LABEL, GOT_LABEL],
    }
    for out_dir in outputs:
        out_dir.mkdir(parents=True, exist_ok=True)
        for old_plot in out_dir.glob(f"pass_{PASS_NUMBER:03d}_*.png"):
            old_plot.unlink()

    n_written = 0
    for r in range(BOX_SIZE):
        for c in range(BOX_SIZE):
            if all(np.all(np.isnan(fields[label][:, r, c])) for label in (SSH_LABEL, SSH1_LABEL)):
                print(f"  [SKIP] pixel r{r} c{c}: no cycles with qual = 0")
                continue
            for out_dir, labels in outputs.items():
                panels = [(label, fields[label][:, r, c]) for label in labels]
                plot_pixel(times, panels, box_lat[r, c], box_lon[r, c], r, c, out_dir)
            n_written += 1

    for out_dir, labels in outputs.items():
        plot_overview(times, [(label, fields[label]) for label in labels], box_lat, box_lon, out_dir)
        print(f"Wrote {n_written} pixel plots + 1 overview to {out_dir}")
