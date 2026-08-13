#!/usr/bin/env python3
"""只读验证材料光学计算和后处理输出（mc-v0.5）。

Checks OUTCAR/vasprun.xml/WAVECAR/WAVEDER, the dielectric blocks, the
energy-domain and wavelength-domain CSVs (all six quantity columns:
eps1_avg, eps2_avg, n, k, alpha_cm-1, reflectivity), monotonic energy,
zero-energy wavelength handling, finite values, non-negative n/k/alpha,
0 <= R <= 1, sorted wavelength CSV, and the presence of all six
energy-domain PNGs, the wavelength-domain PNGs and the windowed
alpha/reflectivity views in EITHER the mc-v0.1 naming set or the
template legacy naming set. Prints VALIDATION=PASS on success.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_loader import load_config  # noqa: E402


def fail(message: str):
    raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--run-dir", type=Path, default=None, help="override run dir")
    args = parser.parse_args()

    config = load_config(args.config)
    run = config["run"]
    prefix = run["prefix"]
    optics_dir = Path(run["output_dir"]) / "01_LOPTICS"
    run_dir = args.run_dir or optics_dir

    required = [
        "OUTCAR", "vasprun.xml", "WAVECAR", "WAVEDER",
        f"{prefix}_optical_properties.csv",
        f"{prefix}_optical_properties_wavelength.csv",
    ]
    for name in required:
        path = run_dir / name
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"Missing or empty required file: {path}")

    outcar = (run_dir / "OUTCAR").read_text(errors="replace")
    if "General timing and accounting" not in outcar:
        fail("OUTCAR has no final timing block; the VASP run may be incomplete.")
    if "frequency dependent IMAGINARY DIELECTRIC FUNCTION" not in outcar:
        fail("OUTCAR has no frequency-dependent imaginary dielectric function.")
    if "frequency dependent      REAL DIELECTRIC FUNCTION" not in outcar:
        fail("OUTCAR has no frequency-dependent real dielectric function.")

    root = ET.parse(run_dir / "vasprun.xml").getroot()
    blocks = root.findall(".//dielectricfunction")
    if not blocks:
        fail("vasprun.xml has no dielectricfunction element.")
    selected_response = config["parameters"].get("response", "density-density")
    responses = {b.attrib.get("comment", "") for b in blocks}
    if selected_response not in responses:
        fail(f"Selected response {selected_response!r} is absent; found {sorted(responses)}")

    quantity_columns = [
        "eps1_avg", "eps2_avg", "n", "k", "alpha_cm-1", "reflectivity",
    ]
    energy_csv = run_dir / f"{prefix}_optical_properties.csv"
    with energy_csv.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) < 10:
        fail(f"Energy CSV contains too few rows: {len(rows)}")
    required_columns = {"energy_eV", "wavelength_nm"} | set(quantity_columns)
    missing = required_columns - set(rows[0])
    if missing:
        fail(f"Energy CSV is missing columns: {sorted(missing)}")

    energies = [float(row["energy_eV"]) for row in rows]
    if any(b <= a for a, b in zip(energies, energies[1:])):
        fail("energy_eV is not strictly increasing.")
    for index, row in enumerate(rows):
        for column in ("energy_eV", *quantity_columns):
            value = float(row[column])
            if not math.isfinite(value):
                fail(f"Non-finite value in {column} at row {index}.")
        wavelength = float(row["wavelength_nm"]) if row["wavelength_nm"] else math.nan
        if index == 0 and energies[index] == 0:
            if not math.isnan(wavelength):
                fail("The zero-energy wavelength should be NaN.")
        elif not math.isfinite(wavelength):
            fail(f"Non-finite wavelength at row {index}.")
        if float(row["n"]) < 0 or float(row["k"]) < 0 or float(row["alpha_cm-1"]) < 0:
            fail(f"Negative n/k/alpha value at row {index}.")
        reflectivity = float(row["reflectivity"])
        if not 0 <= reflectivity <= 1:
            fail(f"Reflectivity outside [0,1] at row {index}: {reflectivity}")

    wavelength_csv = run_dir / f"{prefix}_optical_properties_wavelength.csv"
    with wavelength_csv.open(newline="") as handle:
        wrows = list(csv.DictReader(handle))
    if len(wrows) < 10:
        fail(f"Wavelength CSV contains too few rows: {len(wrows)}")
    wmissing = required_columns - set(wrows[0])
    if wmissing:
        fail(f"Wavelength CSV is missing columns: {sorted(wmissing)}")
    wavelengths = [float(row["wavelength_nm"]) for row in wrows]
    if any(b <= a for a, b in zip(wavelengths, wavelengths[1:])):
        fail("wavelength_nm is not strictly increasing in the wavelength CSV.")
    for index, row in enumerate(wrows):
        for column in quantity_columns:
            if not math.isfinite(float(row[column])):
                fail(f"Non-finite value in {column} at wavelength row {index}.")

    # All six energy-domain PNGs (identical naming in the mc-v0.1 and the
    # template legacy naming sets).
    energy_pngs = ["epsilon1", "epsilon2", "n", "k", "alpha", "R"]
    for base in energy_pngs:
        path = run_dir / f"{prefix}_{base}.png"
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"Missing plot output: {path}")

    # Wavelength-domain PNGs and windowed alpha/reflectivity views. Accept
    # EITHER the mc-v0.1 naming set (plot.py default output: eps1/eps2 plus
    # all six quantities, and the alpha log-y view) OR the template legacy
    # naming set (alpha/R/n/k only, no eps1/eps2, no alpha log-y view).
    # All other validation checks are unchanged.
    mc_v01_wavelength_pngs = [
        "eps1_vs_wavelength", "eps2_vs_wavelength", "n_vs_wavelength",
        "k_vs_wavelength", "alpha_vs_wavelength", "R_vs_wavelength",
    ]
    legacy_wavelength_pngs = [
        "alpha_vs_wavelength", "R_vs_wavelength", "n_vs_wavelength",
        "k_vs_wavelength",
    ]
    mc_v01_extra_pngs = [
        "alpha_300_2500nm.png", "alpha_300_2500nm_log.png", "R_300_2500nm.png",
    ]
    legacy_extra_pngs = ["alpha_300_2500nm.png", "R_300_2500nm.png"]

    def missing_plots(bases, suffix=""):
        missing = []
        for base in bases:
            path = run_dir / f"{prefix}_{base}{suffix}"
            if not path.is_file() or path.stat().st_size == 0:
                missing.append(str(path))
        return missing

    mc_v01_missing = (
        missing_plots(mc_v01_wavelength_pngs, ".png")
        + missing_plots(mc_v01_extra_pngs)
    )
    legacy_missing = (
        missing_plots(legacy_wavelength_pngs, ".png")
        + missing_plots(legacy_extra_pngs)
    )
    if mc_v01_missing and legacy_missing:
        fail(
            "Incomplete plot set: mc-v0.1 naming missing "
            f"{mc_v01_missing}; template legacy naming missing {legacy_missing}"
        )

    print(f"VALIDATION=PASS;MATERIAL={run.get('material', prefix)};ROWS={len(rows)};RESPONSE={selected_response};RESPONSES={sorted(responses)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ET.ParseError, ValueError) as exc:
        print(f"VALIDATION=FAIL;{exc}", file=sys.stderr)
        raise SystemExit(1)
