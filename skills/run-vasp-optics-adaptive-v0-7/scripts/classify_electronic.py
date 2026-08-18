#!/usr/bin/env python3
"""Classify a finished VASP ground state from its actual eigenvalues.

The result is a reviewable JSON record used as a gate before LOPTICS.  It
does not infer electronic type from a material name or from POSCAR alone.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_loader import load_config  # noqa: E402


def _last_float(root: ET.Element, name: str) -> float | None:
    values = []
    for node in root.findall(f".//i[@name='{name}']"):
        if node.text:
            try:
                values.append(float(node.text.split()[0]))
            except ValueError:
                pass
    return values[-1] if values else None


def _leaf_eigenvalue_sets(root: ET.Element) -> list[list[tuple[float, float]]]:
    eigen_blocks = root.findall(".//eigenvalues")
    if not eigen_blocks:
        raise RuntimeError("vasprun.xml has no eigenvalues block")
    leaves: list[list[tuple[float, float]]] = []
    for node in eigen_blocks[-1].findall(".//set"):
        rows: list[tuple[float, float]] = []
        for row in node.findall("r"):
            if not row.text:
                continue
            values = row.text.split()
            if len(values) >= 2:
                rows.append((float(values[0]), float(values[1])))
        if rows:
            leaves.append(rows)
    if not leaves:
        raise RuntimeError("vasprun.xml eigenvalues block has no numerical k-point sets")
    return leaves


def classify_ground_state(config: dict, xml_path: Path) -> dict:
    root = ET.parse(xml_path).getroot()
    leaves = _leaf_eigenvalue_sets(root)
    efermi = _last_float(root, "efermi")
    occupations = [occupation for leaf in leaves for _, occupation in leaf]
    full_occupation = 2.0 if max(occupations) > 1.1 else 1.0
    settings = config.get("classification", {})
    occ_tol = float(settings.get("occupation_tolerance", 1e-3))
    gap_threshold = float(settings.get("gap_threshold_eV", 0.05))
    insulator_threshold = float(settings.get("insulator_gap_threshold_eV", 3.0))

    fractional = any(
        occ_tol < occupation < full_occupation - occ_tol
        for occupation in occupations
    )
    occupied = [
        energy for leaf in leaves for energy, occupation in leaf
        if occupation >= full_occupation - occ_tol
    ]
    empty = [
        energy for leaf in leaves for energy, occupation in leaf
        if occupation <= occ_tol
    ]
    vbm = max(occupied) if occupied else None
    cbm = min(empty) if empty else None
    occupied_empty_separation = max(0.0, cbm - vbm) if vbm is not None and cbm is not None else None

    crossing = False
    if efermi is not None:
        max_bands = max(len(leaf) for leaf in leaves)
        for band in range(max_bands):
            energies = [leaf[band][0] for leaf in leaves if band < len(leaf)]
            if energies and min(energies) < efermi - gap_threshold and max(energies) > efermi + gap_threshold:
                crossing = True
                break

    if fractional or crossing or occupied_empty_separation is None or occupied_empty_separation <= gap_threshold:
        electronic_class = "metal-or-semimetal"
    elif occupied_empty_separation >= insulator_threshold:
        electronic_class = "insulator"
    else:
        electronic_class = "semiconductor"
    gap = 0.0 if electronic_class == "metal-or-semimetal" else occupied_empty_separation

    structure = config.get("_metadata", {}).get("classification", {})
    warnings: list[str] = []
    if electronic_class == "metal-or-semimetal":
        warnings.append(
            "A metal/semimetal needs an explicit decision: stop, interband-only, or a user-approved Drude broadening."
        )
    if structure.get("structure_class") != "bulk-3d-candidate":
        warnings.append(
            "For a non-bulk supercell, epsilon/n/k/alpha/R depend on the vacuum volume and are not intrinsic bulk constants."
        )
    return {
        "schema_version": 1,
        "source": str(xml_path),
        "structure_class": structure.get("structure_class", "unknown"),
        "electronic_class": electronic_class,
        "efermi_eV": efermi,
        "vbm_eV": vbm,
        "cbm_eV": cbm,
        "estimated_gap_eV": gap,
        "fully_occupied_to_empty_separation_eV": occupied_empty_separation,
        "fractional_occupations_detected": fractional,
        "fermi_crossing_detected": crossing,
        "full_occupation": full_occupation,
        "kpoint_spin_sets": len(leaves),
        "gap_threshold_eV": gap_threshold,
        "warnings": warnings,
        "decision": "Review this report and set run.confirm_electronic_classification=true before LOPTICS.",
    }


def write_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--xml", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    output_dir = Path(config["run"]["output_dir"])
    xml_path = args.xml or output_dir / "00_DFT" / "vasprun.xml"
    out_path = args.out or output_dir / "system_classification.json"
    if not xml_path.is_file():
        raise SystemExit(f"CLASSIFY=FAIL;missing ground-state XML: {xml_path}")
    try:
        report = classify_ground_state(config, xml_path)
        write_report(report, out_path)
    except (ET.ParseError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"CLASSIFY=FAIL;{exc}") from exc
    gap = report.get("estimated_gap_eV")
    gap_text = "unknown" if gap is None or not math.isfinite(gap) else f"{gap:.6f}"
    print(
        f"CLASSIFY=OK;STRUCTURE_CLASS={report['structure_class']};"
        f"ELECTRONIC_CLASS={report['electronic_class']};GAP_EV={gap_text};REPORT={out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
