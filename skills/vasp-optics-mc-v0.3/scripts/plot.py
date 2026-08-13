#!/usr/bin/env python3
"""为六个光学量生成波长域 CSV/PNG（mc-v0.2）。

Uses lambda(nm) = 1239.841984 / E(eV), removes the zero-energy row, sorts
by wavelength, writes <prefix>_optical_properties_wavelength.csv, and
produces six wavelength-domain PNGs plus 300-2500 nm views for alpha and
reflectivity (linear and log-y for alpha).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_loader import load_config  # noqa: E402

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
except ImportError as exc:
    raise SystemExit(
        "Missing wavelength-plot dependency. Activate the optics conda "
        "environment and install numpy/pandas/matplotlib."
    ) from exc

SIX_QUANTITIES = [
    ("eps1_avg", r"$\epsilon_1$"),
    ("eps2_avg", r"$\epsilon_2$"),
    ("n", "Refractive index n"),
    ("k", "Extinction coefficient k"),
    ("alpha_cm-1", r"Absorption coefficient $\alpha$ (cm$^{-1}$)"),
    ("reflectivity", "Reflectivity R"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--csv", type=Path, default=None, help="override energy CSV")
    parser.add_argument("--outdir", type=Path, default=None, help="override output dir")
    parser.add_argument("--xmin", type=float, default=300.0)
    parser.add_argument("--xmax", type=float, default=2500.0)
    args = parser.parse_args()

    config = load_config(args.config)
    run = config["run"]
    prefix = run["prefix"]
    material = run.get("material", prefix)
    optics_dir = Path(run["output_dir"]) / "01_LOPTICS"
    csv_path = args.csv or optics_dir / f"{prefix}_optical_properties.csv"
    outdir = args.outdir or optics_dir

    if not csv_path.is_file():
        raise SystemExit(f"CSV does not exist: {csv_path}")
    outdir.mkdir(parents=True, exist_ok=True)

    data = pd.read_csv(csv_path)
    required = {"energy_eV", "eps1_avg", "eps2_avg", "n", "k", "alpha_cm-1", "reflectivity"}
    missing = required - set(data.columns)
    if missing:
        raise SystemExit(f"CSV is missing columns: {sorted(missing)}")
    data = data[np.isfinite(data["energy_eV"]) & (data["energy_eV"] > 1e-12)].copy()
    data["wavelength_nm"] = 1239.841984 / data["energy_eV"]
    data = data.sort_values("wavelength_nm")
    wavelength_csv = outdir / f"{prefix}_optical_properties_wavelength.csv"
    data.to_csv(wavelength_csv, index=False)

    def make_plot(column: str, ylabel: str, filename: str, xlim=None, log_y=False):
        x = data["wavelength_nm"].to_numpy(float)
        y = data[column].to_numpy(float)
        valid = np.isfinite(x) & np.isfinite(y)
        if log_y:
            valid &= y > 0
        fig, ax = plt.subplots(figsize=(7.0, 4.8))
        ax.plot(x[valid], y[valid], linewidth=1.5)
        ax.set_xscale("log")
        if log_y:
            ax.set_yscale("log")
        ax.set_xlabel("Wavelength (nm)")
        ax.set_ylabel(ylabel)
        ax.set_title(f"{material} {ylabel} versus wavelength")
        ax.grid(alpha=0.25, which="both")
        if xlim:
            ax.set_xlim(*xlim)
        fig.tight_layout()
        fig.savefig(outdir / filename, dpi=220)
        plt.close(fig)

    # Six wavelength-domain PNGs (epsilon1, epsilon2, n, k, alpha, R)
    # Filename stems must match what validate.py expects (template-compatible).
    filename_stem = {
        "eps1_avg": "eps1",
        "eps2_avg": "eps2",
        "n": "n",
        "k": "k",
        "alpha_cm-1": "alpha",
        "reflectivity": "R",
    }
    for column, ylabel in SIX_QUANTITIES:
        filename = f"{prefix}_{filename_stem[column]}_vs_wavelength.png"
        make_plot(column, ylabel, filename)

    # 300-2500 nm views for alpha and reflectivity (matching template behaviour)
    make_plot("alpha_cm-1", r"Absorption coefficient $\alpha$ (cm$^{-1}$)",
              f"{prefix}_alpha_{int(args.xmin)}_{int(args.xmax)}nm.png",
              (args.xmin, args.xmax))
    make_plot("alpha_cm-1", r"Absorption coefficient $\alpha$ (cm$^{-1}$)",
              f"{prefix}_alpha_{int(args.xmin)}_{int(args.xmax)}nm_log.png",
              (args.xmin, args.xmax), log_y=True)
    make_plot("reflectivity", "Reflectivity R",
              f"{prefix}_R_{int(args.xmin)}_{int(args.xmax)}nm.png",
              (args.xmin, args.xmax))

    print(f"WAVELENGTH_POSTPROCESS=OK;ROWS={len(data)};"
          f"RANGE_NM={data.wavelength_nm.min():.6g}:{data.wavelength_nm.max():.6g}")
    print(f"CSV={wavelength_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
