import contextlib
import io
import warnings

import matplotlib.pyplot as plt
import numpy as np

from swot_timeseries_tide_maputo_bay import (
    FES_LABEL, GOT_LABEL, PASS_NUMBER, SSH_LABEL,
    format_time_axis, latest_file_per_cycle, load_timeseries,
)
from pathlib import Path

# Basic astronomical speeds (deg/hour) from the Stony Brook page
T_SPEED = 15.0
H_SPEED = 0.04106864
S_SPEED = 0.54901653
M2_SPEED = 2 * T_SPEED - 2 * S_SPEED + 2 * H_SPEED  # 28.984104 deg/hour

# t = 0 for the fit; phi is relative to this epoch
EPOCH = np.datetime64("2023-01-01T00:00:00")

OUT_DIR = Path(__file__).resolve().parent / "harmonic_analysis_plots"

TIDE_STYLES = {  # label -> (short name, marker, color)
    FES_LABEL: ("FES", "s", "#295e11"),
    GOT_LABEL: ("GOT", "^", "#58094f"),
}

# (SSH field, its tide fields, short name) -- one M2 fit and two figure rows each
VARIANTS = [
    (SSH_LABEL, (FES_LABEL, GOT_LABEL), "ssh_karin_2"),
]


def box_means():
    """Per-cycle box means of every SSH variant and its tide fields."""
    with contextlib.redirect_stdout(io.StringIO()):
        _, times, fields, _, _ = load_timeseries(latest_file_per_cycle())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN cycles
        means = {label: np.nanmean(vals.reshape(len(times), -1), axis=1)
                 for label, vals in fields.items()}
    return times, means


def fit_variant(times, means, ssh_label, tide_labels):
    """M2 fit to one SSH variant; returns everything its two figure rows need."""
    valid = ~np.isnan(means[ssh_label])
    ssh = means[ssh_label][valid]
    t_hours = hours_since_epoch(times[valid])
    z0, amplitude, phase = fit_m2(t_hours, ssh)
    return {
        "times": times[valid],
        "ssh": ssh,
        "m2_term": z0 + m2(t_hours, amplitude, phase),
        "tides": {label: z0 + means[label][valid] for label in tide_labels},
        "z0": z0,
        "fit_label": f"{z0:.3f} + {amplitude:.3f} cos({M2_SPEED:.6f} t + {phase:.2f}°)",
        "summary": (f"n cycles = {valid.sum()}\nZ0 = {z0:.3f} m\n"
                    f"SSH std = {ssh.std():.3f} m"),
    }


def hours_since_epoch(times):
    return (times - EPOCH) / np.timedelta64(1, "h")


def m2(t_hours, amplitude, phase_deg):
    return amplitude * np.cos(np.radians(M2_SPEED * t_hours + phase_deg))


def fit_m2(t_hours, y):
    """OLS for y = Z0 + A cos(at) + B sin(at); returns Z0, H, phi (deg)."""
    arg = np.radians(M2_SPEED * t_hours)
    design = np.column_stack([np.ones_like(arg), np.cos(arg), np.sin(arg)])
    (z0, a_coef, b_coef), *_ = np.linalg.lstsq(design, y, rcond=None)
    amplitude = np.hypot(a_coef, b_coef)
    phase = np.degrees(np.arctan2(-b_coef, a_coef)) % 360
    return z0, amplitude, phase


def regress(y, x):
    """OLS of y = b0 + b1 x. Returns b0, b1 and R² = 1 - RSS/TSS (0 to 1)."""
    design = np.column_stack([np.ones_like(x), x])
    (b0, b1), *_ = np.linalg.lstsq(design, y, rcond=None)
    rss = np.sum((y - (b0 + b1 * x)) ** 2)
    tss = np.sum((y - y.mean()) ** 2)
    return b0, b1, 1 - rss / tss


def fit_stats(y, x):
    """R² of the OLS regression of y on x."""
    _, _, r2 = regress(y, x)
    return f"R² = {r2:.3f}"


def draw_regression(ax, y, x, color):
    """Draw the OLS fit of y on x across the span of the data."""
    b0, b1, _ = regress(y, x)
    x_edges = np.array([x.min(), x.max()])
    ax.plot(x_edges, b0 + b1 * x_edges, color=color, linewidth=3)


def plot_variant_rows(axes, variant, name):
    """Fill two rows (time series + scatter) for one SSH variant."""
    times, ssh = variant["times"], variant["ssh"]
    m2_term, tides, fit_label = variant["m2_term"], variant["tides"], variant["fit_label"]
    z0 = variant["z0"]

    # left column: SSH box mean, the fit and one tide model per row (FES top, GOT bottom)
    for ax, (label, tide) in zip(axes[:, 0], tides.items()):
        tide_name, marker, color = TIDE_STYLES[label]
        ax.plot(times, ssh, "o", linestyle="dotted", color="k", markersize=4, linewidth=0.8,
                label=f"{name} box mean")
        ax.axhline(z0, color="0.5", linestyle="--", linewidth=0.8, label=f"Z0 = {z0:.3f} m")
        ax.plot(times, m2_term, "o", color="tab:blue", markersize=4, label=f"M2 fit: {fit_label}")
        ax.plot(times, tide, marker, color=color, markersize=5, label=f"{tide_name} box mean + Z0")
        ax.set_ylabel("height (m)")
        ax.set_title(f"{name}: SSH box mean, M2 fit and {tide_name} at SWOT overpass times",
                     fontsize=10)
        format_time_axis(ax)
        lo, hi = ax.get_ylim()
        ax.set_ylim(lo - 0.25 * (hi - lo), hi)  # room for the legend below the data
        ax.legend(fontsize=8, loc="lower left", ncols=2)

    # first right panel: the M2 fit regressed on the SSH box mean
    ax = axes[0, 1]
    ax.scatter(ssh, m2_term, s=18, color="tab:blue",
               label=f"M2 fit\n{variant['summary']}\n{fit_stats(m2_term, ssh)}")
    draw_regression(ax, m2_term, ssh, "tab:blue")
    ax.set_ylabel("M2 fit Z0 + H cos(at + φ) (m)")
    ax.set_title(f"{name}: M2 fit vs SSH box mean", fontsize=10)

    # second right panel: tide models regressed on the SSH box mean
    ax = axes[1, 1]
    for label, tide in tides.items():
        tide_name, marker, color = TIDE_STYLES[label]
        ax.scatter(ssh, tide, s=22, marker=marker, color=color,
                   label=f"{tide_name}\n{fit_stats(tide, ssh)}")
        draw_regression(ax, tide, ssh, color)
    ax.set_ylabel("tide model box mean + Z0 (m)")
    ax.set_title(f"{name}: FES / GOT vs SSH box mean", fontsize=10)

    for ax in axes[:, 1]:
        ax.set_xlabel(f"{name} box mean (m)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=10, bbox_to_anchor=(1.00, 0.75), loc='center left')


def plot_fits(variants, summary):
    """variants: list of (name, fitted variant dict); two rows per variant."""
    fig, axes = plt.subplots(
        2 * len(variants), 2, figsize=(17, 4.5 * 2 * len(variants)),
        gridspec_kw={"width_ratios": [2.3, 1]}, constrained_layout=True,
    )
    for k, (name, variant) in enumerate(variants):
        plot_variant_rows(axes[2 * k:2 * k + 2], variant, name)
    fig.suptitle(f"Pass {PASS_NUMBER} Maputo Bay box M2 harmonic analysis\n{summary}", fontsize=10)
    out_path = OUT_DIR / f"maputo_bay_pass_{PASS_NUMBER:03d}_tide_model_comparison.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    times, means = box_means()

    fitted = [(name, fit_variant(times, means, ssh_label, tide_labels))
              for ssh_label, tide_labels, name in VARIANTS]
    summary = (f"t = 0 at {EPOCH} UTC   "
               f"M2 speed = {M2_SPEED:.6f} °/h ({360 / M2_SPEED:.4f} h)")

    for name, variant in fitted:
        print(f"[{name}] M2 fit: {variant['fit_label']}   {variant['summary']}")
        print(f"    M2 fit vs SSH box mean: {fit_stats(variant['m2_term'], variant['ssh'])}")
        for label, tide in variant["tides"].items():
            print(f"    {TIDE_STYLES[label][0]} + Z0 vs SSH box mean: {fit_stats(tide, variant['ssh'])}")
    print(summary)
    print(f"Wrote {plot_fits(fitted, summary)}")
