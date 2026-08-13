#!/usr/bin/env python3
"""提取介电函数并计算六个光学量（mc-v0.2）。

Reads the fixed `density-density` response from vasprun.xml (configurable
via config.yaml `parameters.response`), averages the diagonal tensor
elements, derives n/k/alpha/R, and writes:

  <prefix>_optical_properties.csv          (energy + wavelength columns)
  <prefix>_epsilon1.png, <prefix>_epsilon2.png
  <prefix>_n.png, <prefix>_k.png, <prefix>_alpha.png, <prefix>_R.png

This is independent-particle LOPTICS without excitons, local-field
corrections, spin-orbit coupling, or magnetic effects.
"""

from __future__ import annotations

import argparse
import csv
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_loader import load_config  # noqa: E402

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError as exc:
    raise SystemExit(
        "Missing post-processing dependency. Activate the optics conda "
        "environment and install numpy/matplotlib."
    ) from exc

EV_TO_J = 1.602176634e-19
HBAR = 1.054571817e-34
C = 299792458.0


def read_section(block: ET.Element, name: str) -> np.ndarray:
    section = block.find(name)
    if section is None:
        raise RuntimeError(f"Cannot find <{name}> in the selected dielectric block.")
    rows = []
    for node in section.findall(".//r"):
        if node.text:
            values = [float(x) for x in node.text.split()]
            if len(values) >= 7:
                rows.append(values[:7])
    if not rows:
        raise RuntimeError(f"No numerical rows found in <{name}>.")
    return np.asarray(rows, dtype=float)


def choose_block(root: ET.Element, response: str) -> ET.Element:
    blocks = root.findall(".//dielectricfunction")
    available = [b.attrib.get("comment", "") for b in blocks]
    for block in blocks:
        if block.attrib.get("comment", "").strip() == response:
            return block
    raise RuntimeError(
        f'No dielectricfunction comment="{response}". Available responses: {available}'
    )


def align(real: np.ndarray, imag: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if len(real) == len(imag) and np.allclose(real[:, 0], imag[:, 0]):
        return real, imag
    real_new = np.empty_like(imag)
    real_new[:, 0] = imag[:, 0]
    for col in range(1, 7):
        real_new[:, col] = np.interp(imag[:, 0], real[:, 0], real[:, col])
    return real_new, imag


def derive(energy: np.ndarray, eps1: np.ndarray, eps2: np.ndarray):
    magnitude = np.sqrt(eps1 * eps1 + eps2 * eps2)
    n = np.sqrt(np.clip((magnitude + eps1) / 2.0, 0.0, None))
    kappa = np.sqrt(np.clip((magnitude - eps1) / 2.0, 0.0, None))
    omega = energy * EV_TO_J / HBAR
    alpha_cm = 2.0 * omega * kappa / C / 100.0
    reflectivity = (((n - 1.0) ** 2 + kappa ** 2) /
                    ((n + 1.0) ** 2 + kappa ** 2))
    wavelength_nm = np.full_like(energy, np.nan)
    positive = energy > 1e-12
    wavelength_nm[positive] = 1239.841984 / energy[positive]
    return n, kappa, alpha_cm, reflectivity, wavelength_nm


def save_plot(x, y, ylabel: str, path: Path, title: str):
    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    ax.plot(x, y, linewidth=1.5)
    ax.set_xlabel("Photon energy (eV)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument(
        "--xml",
        type=Path,
        default=None,
        help="override vasprun.xml path (default: <output_dir>/01_LOPTICS/vasprun.xml)",
    )
    parser.add_argument(
        "--outdir", type=Path, default=None, help="override output directory"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    run = config["run"]
    parameters = config["parameters"]
    prefix = run["prefix"]
    material = run.get("material", prefix)
    response = parameters["response"]
    optics_dir = Path(run["output_dir"]) / "01_LOPTICS"
    xml_path = args.xml or optics_dir / "vasprun.xml"
    outdir = args.outdir or optics_dir

    if not xml_path.is_file():
        raise SystemExit(f"Input XML does not exist: {xml_path}")
    outdir.mkdir(parents=True, exist_ok=True)

    root = ET.parse(xml_path).getroot()
    block = choose_block(root, response)
    real, imag = align(read_section(block, "real"), read_section(block, "imag"))
    energy = imag[:, 0]
    eps1 = real[:, 1:4]
    eps2 = imag[:, 1:4]
    eps1_avg = eps1.mean(axis=1)
    eps2_avg = eps2.mean(axis=1)
    n, kappa, alpha_cm, reflectivity, wavelength_nm = derive(energy, eps1_avg, eps2_avg)

    rows = np.column_stack([
        energy, wavelength_nm,
        real[:, 1], real[:, 2], real[:, 3], real[:, 4], real[:, 5], real[:, 6],
        imag[:, 1], imag[:, 2], imag[:, 3], imag[:, 4], imag[:, 5], imag[:, 6],
        eps1_avg, eps2_avg, n, kappa, alpha_cm, reflectivity,
    ])
    header = [
        "energy_eV", "wavelength_nm",
        "eps1_xx", "eps1_yy", "eps1_zz", "eps1_xy", "eps1_yz", "eps1_zx",
        "eps2_xx", "eps2_yy", "eps2_zz", "eps2_xy", "eps2_yz", "eps2_zx",
        "eps1_avg", "eps2_avg", "n", "k", "alpha_cm-1", "reflectivity",
    ]
    csv_path = outdir / f"{prefix}_optical_properties.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)

    save_plot(energy, eps1_avg, r"$\epsilon_1(\omega)$",
              outdir / f"{prefix}_epsilon1.png", f"{material} Real Dielectric Function")
    save_plot(energy, eps2_avg, r"$\epsilon_2(\omega)$",
              outdir / f"{prefix}_epsilon2.png", f"{material} Imaginary Dielectric Function")
    save_plot(energy, n, "Refractive index n",
              outdir / f"{prefix}_n.png", f"{material} Refractive Index")
    save_plot(energy, kappa, "Extinction coefficient k",
              outdir / f"{prefix}_k.png", f"{material} Extinction Coefficient")
    save_plot(energy, alpha_cm, r"Absorption coefficient $\alpha$ (cm$^{-1}$)",
              outdir / f"{prefix}_alpha.png", f"{material} Absorption Coefficient")
    save_plot(energy, reflectivity, "Reflectivity R",
              outdir / f"{prefix}_R.png", f"{material} Normal-Incidence Reflectivity")

    print(f"EXTRACT=OK;MATERIAL={material};RESPONSE={response};ROWS={len(energy)};"
          f"ENERGY={energy.min():.6g}:{energy.max():.6g}")
    print(f"CSV={csv_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ET.ParseError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"Extraction failed: {exc}") from exc
