#!/usr/bin/env python3
"""Inspect VASP optics inputs and derive reviewable, system-based defaults.

This version deliberately does not select parameters by material name.  It
uses the supplied POSCAR, POTCAR and KPOINTS to classify the structural
setting, reports what is still uncertain, and fills only values marked
``auto``.  Structural classification happens before VASP; electronic
classification is deliberately deferred until the ground-state result exists.
No VASP command is run by this module.
"""

from __future__ import annotations

import argparse
import copy
import math
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required for config_loader.py") from exc


AUTO = {"", "auto", "automatic", "default", "none", "null"}

RUN_DEFAULTS = {
    "input_dir": "./inputs",
    "existing_dft_dir": "",
    "output_dir": "./stage1_demo",
    "material": "auto",
    "prefix": "auto",
    "expected_elements": [],
    "system_hint": "auto",  # auto, insulator, semiconductor, metal
    "confirm_recommendations": False,
    "confirm_electronic_classification": False,
    "allow_nonbulk_supercell_optics": False,
    "metal_optics_mode": "stop",  # stop, interband-only, drude
    "target_max_energy_eV": None,
}

ENV_DEFAULTS = {
    "vasp_bin": "vasp_std",
    "vasp_gamma_bin": "",
    "auto_select_gamma": True,
    "oneapi_setup": "",
    "mpi_launcher": "mpirun",
    "mpi_cores": 4,
    "timeout_seconds": 3600,
    "conda_env": "",
}

PARAMETER_DEFAULTS = {
    "parameter_policy": "preserve-user",
    "encut": "auto",
    "nbands": "auto",
    "kpoints": "auto",
    "kpoints_shift": [0, 0, 0],
    "response": "density-density",
    "encut_policy": "warn",
    "heuristics": {
        "encut_rounding_eV": 10.0,
        "kpoints_density_gapped": 6.0,
        "kpoints_density_metal": 8.0,
        "nbands_minimum": 32,
        "nbands_empty_minimum": 16,
        "nbands_empty_fraction": 0.5,
        "nbands_fallback": 64,
    },
    "dft": {
        "algo": "Normal",
        "ediff": 1e-6,
        "ismear": "auto",
        "sigma": "auto",
        "ispin": "auto",
        "ibrion": -1,
        "nsw": 0,
        "lwave": True,
        "lcharg": True,
    },
    "loptics": {
        "istart": 1,
        "icharg": 11,
        "algo": "Exact",
        "ediff": 1e-8,
        "loptics": True,
        "cshift": "auto",
        "wplasmai": 0.0,
        "nedos": 2000,
        "ismear": "auto",
        "sigma": "auto",
        "ispin": "auto",
        "lwave": True,
        "lcharg": False,
    },
}

CLASSIFICATION_DEFAULTS = {
    "gap_threshold_eV": 0.05,
    "insulator_gap_threshold_eV": 3.0,
    "occupation_tolerance": 1e-3,
    "vacuum_axis_min_angstrom": 6.0,
    "vacuum_axis_aspect_ratio_min": 1.8,
    "slab_aspect_ratio_min": 2.5,
    "isolated_min_cell_angstrom": 10.0,
}

POSTPROCESS_DEFAULTS = {
    "wavelength_constant_nm_eV": 1239.841984,
    "plot_min_nm": 300.0,
    "plot_max_nm": 2500.0,
}

# Elements that make spin polarization a reasonable first suspicion.  This
# is only a flag for human review, not a claim that every such compound is
# magnetic.
MAGNETIC_CANDIDATES = {
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Y", "Zr",
    "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Hf", "Ta", "W", "Re",
    "Os", "Ir", "Pt", "Au", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd",
    "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu", "Th", "Pa", "U", "Np",
    "Pu", "Am", "Cm",
}

# Heavy elements often require an explicit SOC decision.  The list is a
# conservative warning, not an automatic INCAR choice.
SOC_REVIEW_ELEMENTS = {
    "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd",
    "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy",
    "Ho", "Er", "Tm", "Yb", "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt",
    "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn",
}


def _deep_merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _is_auto(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip().lower() in AUTO)


def _float_after(text: str, key: str) -> float | None:
    match = re.search(rf"{re.escape(key)}\s*=\s*([0-9.+Ee-]+)", text)
    return float(match.group(1)) if match else None


def _incar_number(values: dict[str, str], key: str, integer: bool = False):
    if key not in values:
        return None
    token = values[key].split()[0]
    try:
        return int(float(token)) if integer else float(token)
    except ValueError:
        return None


def read_potcar(path: Path) -> list[dict]:
    """Read TITEL, ENMAX and ZVAL from each concatenated POTCAR block."""
    if not path.is_file():
        return []
    blocks: list[dict] = []
    current: dict | None = None
    for line in path.read_text(errors="replace").splitlines():
        if "TITEL" in line and "=" in line:
            if current:
                blocks.append(current)
            title = line.split("=", 1)[1].strip()
            tokens = title.split()
            token = tokens[1] if len(tokens) > 1 else ""
            match = re.match(r"([A-Z][a-z]?)", token)
            current = {"title": title, "element": match.group(1) if match else token}
        elif current is not None and "ENMAX" in line and "=" in line:
            current["enmax"] = _float_after(line, "ENMAX")
        elif current is not None and "ZVAL" in line and "=" in line:
            current["zval"] = _float_after(line, "ZVAL")
    if current:
        blocks.append(current)
    return blocks


def read_poscar(path: Path) -> dict:
    """Read VASP4/VASP5 element names, counts and lattice vectors."""
    lines = [line.strip() for line in path.read_text(errors="replace").splitlines() if line.strip()]
    if len(lines) < 7:
        raise ValueError(f"POSCAR is too short: {path}")
    try:
        scale = float(lines[1])
        vectors = [[float(x) for x in lines[i].split()[:3]] for i in range(2, 5)]
    except (ValueError, IndexError) as exc:
        raise ValueError(f"Cannot read POSCAR lattice vectors: {path}") from exc
    vectors = [[scale * x for x in vector] for vector in vectors]
    tokens = lines[5].split()
    if all(re.fullmatch(r"[+-]?\d+", token) for token in tokens):
        names: list[str] = []
        counts = [int(token) for token in tokens]
    else:
        names = tokens
        counts = [int(token) for token in lines[6].split()]
    return {"elements": names, "counts": counts, "natoms": sum(counts), "lattice": vectors}


def read_kpoints(path: Path) -> dict:
    """Read an explicit Gamma/Monkhorst mesh and shift."""
    lines = [line.strip() for line in path.read_text(errors="replace").splitlines() if line.strip()]
    if len(lines) < 4:
        raise ValueError(f"KPOINTS is too short: {path}")
    mode = lines[2].lower()
    try:
        grid = [int(x) for x in lines[3].split()[:3]]
        shift = [float(x) for x in lines[4].split()[:3]] if len(lines) >= 5 else [0.0, 0.0, 0.0]
    except (ValueError, IndexError) as exc:
        raise ValueError(f"Cannot read KPOINTS mesh: {path}") from exc
    return {"mode": mode, "grid": grid, "shift": shift}


def read_incar(path: Path) -> dict[str, str]:
    """Read a simple INCAR into an upper-case key/value mapping."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(errors="replace").splitlines():
        line = raw_line.split("#", 1)[0].split("!", 1)[0]
        for part in line.split(";"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip().upper()
            value = value.strip()
            if key and value:
                values[key] = value
    return values


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vector))


def _formula(elements: list[str], counts: list[int]) -> str:
    if not elements or len(elements) != len(counts):
        return "unknown-system"
    result = []
    for element, count in zip(elements, counts):
        result.append(element)
        if count != 1:
            result.append(str(count))
    return "".join(result)


def _effective_elements(poscar: dict, potcar: list[dict]) -> list[str]:
    return list(poscar.get("elements") or [x.get("element", "") for x in potcar])


def classify_system(poscar: dict, potcar: list[dict], kpoints: dict, run: dict, settings: dict) -> dict:
    """Classify geometry and flag uncertainty without using material names."""
    elements = _effective_elements(poscar, potcar)
    counts = list(poscar.get("counts") or [])
    lengths = [_norm(v) for v in poscar.get("lattice", [])]
    sorted_lengths = sorted(lengths)
    median = sorted_lengths[1] if len(sorted_lengths) == 3 else (sorted_lengths[-1] if sorted_lengths else 1.0)
    largest = max(lengths) if lengths else 0.0
    ratio = largest / max(median, 1e-9)
    grid = list(kpoints.get("grid") or [1, 1, 1])
    gamma_only = all(int(x) == 1 for x in grid)
    vacuum_min = float(settings.get("vacuum_axis_min_angstrom", 6.0))
    vacuum_ratio = float(settings.get("vacuum_axis_aspect_ratio_min", 1.8))
    slab_ratio = float(settings.get("slab_aspect_ratio_min", 2.5))
    isolated_min = float(settings.get("isolated_min_cell_angstrom", 10.0))
    vacuum_axes = [
        index for index, (length, points) in enumerate(zip(lengths, grid))
        if int(points) == 1
        and length >= vacuum_min
        and length / max(min(lengths), 1e-9) >= vacuum_ratio
    ]

    if gamma_only and lengths and min(lengths) >= isolated_min:
        structure_class = "molecule-or-isolated-candidate"
        structure_note = "Large cell plus Gamma-only sampling suggests an isolated molecule/cluster; bulk optical assumptions need review."
    elif len(vacuum_axes) >= 2:
        structure_class = "wire-or-1d-candidate"
        structure_note = "Two long Gamma-sampled directions suggest a one-dimensional wire; bulk optical constants are cell-volume dependent."
    elif len(vacuum_axes) == 1 or ratio >= slab_ratio or (ratio >= vacuum_ratio and any(int(x) == 1 for x in grid)):
        structure_class = "slab-or-2d-candidate"
        structure_note = "One lattice direction is much longer or sampled only at Gamma; treat it as a possible slab/2D cell."
    else:
        structure_class = "bulk-3d-candidate"
        structure_note = "Lattice lengths and mesh are compatible with a three-dimensional periodic cell."

    hint = str(run.get("system_hint", "auto") or "auto").strip().lower()
    if hint in {"insulator", "semiconductor", "metal"}:
        electronic = hint
        electronic_note = "Electronic character was supplied by the user and will be used for the starting recommendation."
    else:
        electronic = "unknown-needs-dft-check"
        electronic_note = "POSCAR/POTCAR/KPOINTS alone cannot prove a band gap or metallic Fermi surface; confirm with a short ground-state check."

    magnetic_elements = [x for x in elements if x in MAGNETIC_CANDIDATES]
    soc_elements = [x for x in elements if x in SOC_REVIEW_ELEMENTS]
    return {
        "formula": _formula(elements, counts),
        "elements": elements,
        "counts": counts,
        "natoms": poscar.get("natoms"),
        "lattice_lengths": lengths,
        "aspect_ratio": ratio,
        "vacuum_axes": vacuum_axes,
        "kpoints_grid": grid,
        "structure_thresholds": {
            "vacuum_axis_min_angstrom": vacuum_min,
            "vacuum_axis_aspect_ratio_min": vacuum_ratio,
            "slab_aspect_ratio_min": slab_ratio,
            "isolated_min_cell_angstrom": isolated_min,
        },
        "structure_class": structure_class,
        "structure_note": structure_note,
        "electronic_character": electronic,
        "electronic_note": electronic_note,
        "magnetic_candidate": bool(magnetic_elements),
        "magnetic_elements": magnetic_elements,
        "soc_review": bool(soc_elements),
        "soc_elements": soc_elements,
    }


def recommend_parameters(classification: dict, potcar: list[dict], run: dict, parameters: dict) -> dict:
    """Return transparent starting values; these are not convergence proofs."""
    enmax_values = [x.get("enmax") for x in potcar if x.get("enmax") is not None]
    max_enmax = max(enmax_values) if enmax_values else None
    heuristics = parameters.get("heuristics") or {}
    encut_step = float(heuristics.get("encut_rounding_eV", 10.0))
    encut = math.ceil(max_enmax / encut_step) * encut_step if max_enmax is not None else None
    lengths = classification.get("lattice_lengths") or [1.0, 1.0, 1.0]
    structure = classification["structure_class"]
    electronic = classification["electronic_character"]
    if structure == "molecule-or-isolated-candidate":
        grid = [1, 1, 1]
    else:
        reference = sorted(lengths)[1] if len(lengths) == 3 else max(lengths)
        density = float(
            heuristics.get("kpoints_density_metal", 8.0)
            if electronic == "metal"
            else heuristics.get("kpoints_density_gapped", 6.0)
        )
        grid = [max(1, int(math.ceil(density * reference / max(length, 1e-9)))) for length in lengths]
        if structure in {"slab-or-2d-candidate", "wire-or-1d-candidate"}:
            for vacuum_axis in classification.get("vacuum_axes", []):
                grid[vacuum_axis] = 1

    zval = sum(float(x.get("zval", 0.0) or 0.0) * count for x, count in zip(potcar, classification.get("counts") or []))
    occupied = math.ceil(zval / 2.0) if zval else None
    nbands_minimum = int(heuristics.get("nbands_minimum", 32))
    empty_minimum = int(heuristics.get("nbands_empty_minimum", 16))
    empty_fraction = float(heuristics.get("nbands_empty_fraction", 0.5))
    fallback_nbands = int(heuristics.get("nbands_fallback", 64))
    empty_allowance = max(empty_minimum, int(math.floor((occupied or 0) * empty_fraction)))
    nbands = max(nbands_minimum, occupied + empty_allowance) if occupied else fallback_nbands
    if classification["magnetic_candidate"]:
        ispin = 2
    else:
        ispin = 1
    if electronic == "metal":
        ismear, sigma, cshift = 1, 0.10, 0.20
    else:
        ismear, sigma, cshift = 0, 0.01, 0.10

    recommendations = {
        "encut": encut,
        "nbands": nbands,
        "kpoints_convergence_candidate": grid,
        "kpoints_shift": [0, 0, 0],
        "dft_ismear": ismear,
        "dft_sigma": sigma,
        "ispin": ispin,
        "cshift": cshift,
        "nedos": 2000,
        "response": "density-density",
        "occupied_bands_estimate": occupied,
        "max_potcar_enmax": max_enmax,
        "heuristics_used": copy.deepcopy(heuristics),
    }
    notes = [
        "ENCUT is rounded up from the largest POTCAR ENMAX; perform an ENCUT convergence test before quantitative claims.",
        "Keep the user-supplied KPOINTS as the effective mesh; the geometry-based mesh is only a comparison candidate for convergence testing.",
        "NBANDS includes an empty-band allowance. Increase it when the requested photon-energy window is higher than the available conduction states.",
        "CSHIFT controls spectral broadening and is not a substitute for convergence testing.",
    ]
    if electronic == "unknown-needs-dft-check":
        notes.append("Electronic character is unknown: run the ground-state stage and classify its eigenvalues before choosing the final LOPTICS branch.")
    if classification["magnetic_candidate"]:
        notes.append("Magnetic-element candidate: ISPIN=2 is only a starting suggestion; initial moments and magnetic convergence require user input.")
    if classification["soc_review"]:
        notes.append("Heavy-element candidate: decide explicitly whether SOC is required; this stage-1 skill does not silently enable SOC.")
    if structure != "bulk-3d-candidate":
        notes.append("The detected non-bulk geometry may require a vacuum/cell-volume treatment; confirm that a 3D dielectric tensor is meaningful.")
    return {"values": recommendations, "notes": notes}


def _inputs_available(config: dict) -> bool:
    input_dir = Path(config["run"]["input_dir"])
    return all((input_dir / name).is_file() for name in ("POSCAR", "POTCAR", "KPOINTS"))


def resolve_config(config: dict) -> tuple[list[str], dict]:
    """Resolve auto values in-place and return input problems plus metadata."""
    problems: list[str] = []
    run = config["run"]
    input_dir = Path(run["input_dir"])
    required = [input_dir / name for name in ("POSCAR", "POTCAR", "KPOINTS")]
    if any(not path.is_file() for path in required):
        return [f"Missing input file: {path}" for path in required if not path.is_file()], {}
    try:
        poscar = read_poscar(input_dir / "POSCAR")
        kpoints = read_kpoints(input_dir / "KPOINTS")
    except (OSError, ValueError) as exc:
        return [str(exc)], {}
    potcar = read_potcar(input_dir / "POTCAR")
    input_incar = read_incar(input_dir / "INCAR")
    if not potcar:
        problems.append("POTCAR has no readable TITEL blocks")
    pot_elements = [block.get("element", "") for block in potcar]
    expected = list(run.get("expected_elements") or [])
    if expected and pot_elements != expected:
        problems.append(f"POTCAR order {pot_elements} does not match expected_elements {expected}")
    if poscar["elements"] and pot_elements and poscar["elements"] != pot_elements:
        problems.append(f"POSCAR elements {poscar['elements']} do not match POTCAR order {pot_elements}")
    if len(pot_elements) != len(poscar["counts"]):
        problems.append("The number of POTCAR blocks does not match POSCAR element counts")

    p = config["parameters"]
    numeric_policy_values = {
        "classification.vacuum_axis_min_angstrom": config["classification"].get("vacuum_axis_min_angstrom"),
        "classification.vacuum_axis_aspect_ratio_min": config["classification"].get("vacuum_axis_aspect_ratio_min"),
        "classification.slab_aspect_ratio_min": config["classification"].get("slab_aspect_ratio_min"),
        "classification.isolated_min_cell_angstrom": config["classification"].get("isolated_min_cell_angstrom"),
        **{f"parameters.heuristics.{key}": value for key, value in (p.get("heuristics") or {}).items()},
    }
    policy_invalid = False
    for name, value in numeric_policy_values.items():
        try:
            if float(value) <= 0:
                problems.append(f"{name} must be positive")
                policy_invalid = True
        except (TypeError, ValueError):
            problems.append(f"{name} must be numeric")
            policy_invalid = True
    if policy_invalid:
        return problems, {}
    classification = classify_system(poscar, potcar, kpoints, run, config["classification"])
    recommendation = recommend_parameters(classification, potcar, run, p)
    values = recommendation["values"]
    raw = config.get("_raw_parameters", {})
    raw_dft = raw.get("dft") or {}
    raw_loptics = raw.get("loptics") or {}
    preserve_user = str(p.get("parameter_policy", "preserve-user")) == "preserve-user"
    if _is_auto(p.get("encut")):
        user_encut = _incar_number(input_incar, "ENCUT") if preserve_user else None
        p["encut"] = user_encut if user_encut is not None else values["encut"]
    if _is_auto(p.get("nbands")):
        p["nbands"] = values["nbands"]
    if _is_auto(p.get("kpoints")):
        p["kpoints"] = list(kpoints["grid"])
    if _is_auto(p["dft"].get("ismear")):
        user_value = _incar_number(input_incar, "ISMEAR", integer=True) if preserve_user else None
        p["dft"]["ismear"] = user_value if user_value is not None else values["dft_ismear"]
    if _is_auto(p["dft"].get("sigma")):
        user_value = _incar_number(input_incar, "SIGMA") if preserve_user else None
        p["dft"]["sigma"] = user_value if user_value is not None else values["dft_sigma"]
    if _is_auto(p["dft"].get("ispin")):
        user_value = _incar_number(input_incar, "ISPIN", integer=True) if preserve_user else None
        p["dft"]["ispin"] = user_value if user_value is not None else values["ispin"]
    if preserve_user and "ALGO" in input_incar and "algo" not in raw_dft:
        p["dft"]["algo"] = input_incar["ALGO"]
    if preserve_user and "EDIFF" in input_incar and "ediff" not in raw_dft:
        user_value = _incar_number(input_incar, "EDIFF")
        if user_value is not None:
            p["dft"]["ediff"] = user_value
    for key in ("ismear", "sigma", "ispin"):
        if _is_auto(p["loptics"].get(key)):
            source_key = {"ismear": "ISMEAR", "sigma": "SIGMA", "ispin": "ISPIN"}[key]
            user_value = _incar_number(input_incar, source_key, integer=key in {"ismear", "ispin"}) if preserve_user else None
            p["loptics"][key] = user_value if user_value is not None else values[{"ismear": "dft_ismear", "sigma": "dft_sigma", "ispin": "ispin"}[key]]
    if _is_auto(p["loptics"].get("cshift")):
        p["loptics"]["cshift"] = values["cshift"]
    if _is_auto(run.get("material")):
        run["material"] = classification["formula"]
    if _is_auto(run.get("prefix")):
        run["prefix"] = re.sub(r"[^A-Za-z0-9_.-]+", "_", classification["formula"])

    raw_grid = raw.get("kpoints")
    if not _is_auto(raw_grid) and list(kpoints["grid"]) != list(p["kpoints"]):
        problems.append(f"KPOINTS grid {kpoints['grid']} differs from explicitly configured grid {p['kpoints']}")
    raw_shift = raw.get("kpoints_shift", p.get("kpoints_shift"))
    if raw_shift and any(abs(a - b) > 1e-12 for a, b in zip(kpoints["shift"], raw_shift)):
        problems.append(f"KPOINTS shift {kpoints['shift']} differs from configured shift {raw_shift}")
    mode_normalized = re.sub(r"[^a-z]", "", kpoints["mode"])
    if mode_normalized not in {"g", "gamma", "gammacentered", "monkhorstpack", "m"}:
        problems.append(f"KPOINTS is not an explicit Gamma/Monkhorst mesh: mode={kpoints['mode']}")
    enmax = values["max_potcar_enmax"]
    if enmax is not None and p.get("encut") is not None and float(p["encut"]) < enmax:
        problems.append(f"ENCUT={p['encut']} is below max POTCAR ENMAX={enmax:.3f} eV")

    metadata = {
        "material": run.get("material", classification["formula"]),
        "prefix": run.get("prefix", classification["formula"]),
        "potcar": potcar,
        "poscar": poscar,
        "kpoints": kpoints,
        "input_incar": input_incar,
        "parameter_policy": p.get("parameter_policy"),
        "classification": classification,
        "recommendation": recommendation,
        "max_enmax": values["max_potcar_enmax"],
        "decision_summary": (
            f"System class={classification['structure_class']}; "
            f"electronic character={classification['electronic_character']}. "
            "The supplied KPOINTS remains effective. Other auto values were filled from reviewable heuristics; electronic type remains provisional until the DFT report exists."
        ),
        "recommendations": recommendation["notes"],
    }
    config["_metadata"] = metadata
    return problems, metadata


def load_config(path: str | Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise SystemExit(f"Config file does not exist: {path}")
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    config = {
        "parameters": _deep_merge(PARAMETER_DEFAULTS, raw.get("parameters") or {}),
        "run": _deep_merge(RUN_DEFAULTS, raw.get("run") or {}),
        "environment": _deep_merge(ENV_DEFAULTS, raw.get("environment") or {}),
        "postprocess": _deep_merge(POSTPROCESS_DEFAULTS, raw.get("postprocess") or {}),
        "classification": _deep_merge(CLASSIFICATION_DEFAULTS, raw.get("classification") or {}),
        "_raw_parameters": copy.deepcopy(raw.get("parameters") or {}),
    }
    if _inputs_available(config):
        resolve_config(config)
    return config


def inspect_inputs(config: dict) -> tuple[list[str], dict]:
    return resolve_config(config)


def validate_existing_dft(config: dict) -> list[str]:
    """Validate an optional completed ground-state directory without changing it."""
    run = config["run"]
    raw_path = str(run.get("existing_dft_dir", "") or "").strip()
    if not raw_path:
        return []
    directory = Path(raw_path)
    problems: list[str] = []
    if not directory.is_dir():
        return [f"run.existing_dft_dir is not a directory: {directory}"]
    required = ("POSCAR", "POTCAR", "KPOINTS", "OUTCAR", "vasprun.xml", "WAVECAR", "CHGCAR")
    for name in required:
        path = directory / name
        if not path.is_file() or path.stat().st_size == 0:
            problems.append(f"Existing DFT is missing a non-empty {name}: {path}")
    outcar = directory / "OUTCAR"
    if outcar.is_file() and "General timing and accounting" not in outcar.read_text(errors="replace"):
        problems.append("Existing DFT OUTCAR has no final timing block")
    input_dir = Path(run["input_dir"])
    for name in ("POSCAR", "POTCAR", "KPOINTS"):
        source = input_dir / name
        existing = directory / name
        if source.is_file() and existing.is_file() and source.read_bytes() != existing.read_bytes():
            problems.append(f"Existing DFT {name} differs from run.input_dir/{name}")
    return problems


def validate_prepare(config: dict) -> list[str]:
    problems, _ = inspect_inputs(config)
    problems.extend(validate_existing_dft(config))
    run = config["run"]
    output_dir = Path(run["output_dir"])
    if output_dir.exists():
        problems.append(f"Output directory already exists (refusing to overwrite): {output_dir}")
    if not bool(run.get("confirm_recommendations", False)):
        problems.append("Confirmation required: review --inspect output, then set run.confirm_recommendations: true")
    if str(run.get("metal_optics_mode", "stop")) not in {"stop", "interband-only", "drude"}:
        problems.append("run.metal_optics_mode must be stop, interband-only, or drude")
    return problems


def _print_report(metadata: dict) -> None:
    classification = metadata["classification"]
    recommendation = metadata["recommendation"]
    print(
        f"SYSTEM={classification['formula']};STRUCTURE_CLASS={classification['structure_class']};"
        f"ELECTRONIC_CHARACTER={classification['electronic_character']}"
    )
    print(f"POTCAR_ELEMENTS={[x['element'] for x in metadata['potcar']]};MAX_ENMAX={metadata['max_enmax']}")
    print(f"LATTICE_LENGTHS={classification['lattice_lengths']};KPOINTS_ACTUAL={metadata['kpoints']['grid']}")
    print(f"INPUT_INCAR_KEYS={sorted(metadata.get('input_incar', {}))}")
    print(f"RECOMMENDED={recommendation['values']}")
    for note in recommendation["notes"]:
        print(f"RECOMMENDATION={note}")
    print(f"DECISION={metadata['decision_summary']}")


def _print_existing_dft(config: dict) -> None:
    path = str(config["run"].get("existing_dft_dir", "") or "").strip()
    if path:
        print(f"EXISTING_DFT={path};REUSE_MODE=REQUESTED;SOURCE_WILL_REMAIN_READ_ONLY=true")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--inspect", action="store_true", help="classify inputs and print recommendations without creating files")
    parser.add_argument("--check", action="store_true", help="validate inputs, output path and confirmation gate")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.inspect:
        problems, metadata = inspect_inputs(config)
        problems.extend(validate_existing_dft(config))
        if problems:
            for message in problems:
                print(f"INPUT=INVALID;{message}", file=sys.stderr)
            return 2
        _print_report(metadata)
        _print_existing_dft(config)
        print("INSPECT=OK;NO_FILES_CREATED=true")
        return 0
    if args.check:
        problems, metadata = inspect_inputs(config)
        problems.extend(validate_existing_dft(config))
        output_dir = Path(config["run"]["output_dir"])
        if output_dir.exists():
            problems.append(f"Output directory already exists (refusing to overwrite): {output_dir}")
        if not bool(config["run"].get("confirm_recommendations", False)):
            problems.append("Confirmation required: review --inspect output, then set run.confirm_recommendations: true")
        if problems:
            for message in problems:
                print(f"CONFIG=INVALID;{message}", file=sys.stderr)
            if metadata:
                _print_report(metadata)
            return 3 if any("Confirmation required" in x for x in problems) else 2
        print(f"CONFIG=VALID;OUTPUT={config['run']['output_dir']}")
        _print_report(metadata)
        _print_existing_dft(config)
        return 0
    problems, metadata = inspect_inputs(config)
    if problems:
        for message in problems:
            print(f"INPUT=INVALID;{message}", file=sys.stderr)
        return 2
    p = config["parameters"]
    print(
        "CONFIG=OK;"
        f"ENCUT={p['encut']:g};NBANDS={p['nbands']};"
        f"CSHIFT={p['loptics']['cshift']:.3f};NEDOS={p['loptics']['nedos']};"
        f"KPOINTS={'x'.join(map(str, p['kpoints']))};RESPONSE={p['response']}"
    )
    _print_report(metadata)
    _print_existing_dft(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
