#!/usr/bin/env python3
"""读取并检查 vasp-sic-optics-stage1-mc-v0.2 的配置。

v0.2 保留 SiC demo 的默认值，但不再把这些值当成所有材料的硬编码常量。
程序会检查实际 POSCAR、POTCAR、KPOINTS，并报告材料、赝势、ENMAX、ZVAL
和 k 点信息。用户可以在完成收敛性检查后修改 ENCUT、NBANDS 和 KPOINTS。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing PyYAML: activate the post-processing conda environment "
        "and install pyyaml before using config_loader."
    ) from exc

# Fixed stage-1 parameters, copied verbatim from the validated template
# vasp-sic-optics-stage1. Do not change these via config.yaml.
FIXED_PARAMETERS = {
    "encut": 414,
    "nbands": 64,
    "kpoints": [6, 6, 6],
    "kpoints_shift": [0, 0, 0],
    "response": "density-density",
    "dft": {
        "algo": "Normal",
        "ediff": 1e-6,
        "ismear": 0,
        "sigma": 0.01,
        "ispin": 1,
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
        "cshift": 0.100,
        "nedos": 2000,
        "ismear": 0,
        "sigma": 0.01,
        "ispin": 1,
        "lwave": True,
        "lcharg": False,
    },
}

# Starting profiles based on common VASP examples. They are recommendations,
# not universal constants; the real POTCAR and KPOINTS remain authoritative.
MATERIAL_PROFILES = {
    "si": {
        "name": "Si",
        "elements": ["Si"],
        "class": "elemental semiconductor",
        "kpoints": [8, 8, 8],
        "nbands": 64,
        "notes": "Small cubic semiconductor; test 8x8x8 and denser meshes for peak positions.",
    },
    "sic": {
        "name": "SiC",
        "elements": ["Si", "C"],
        "class": "binary semiconductor",
        "kpoints": [6, 6, 6],
        "nbands": 64,
        "notes": "Validated demo profile; compare 8x8x8 and NBANDS 96/128 before quantitative peaks.",
    },
    "gaas": {
        "name": "GaAs",
        "elements": ["Ga", "As"],
        "class": "binary semiconductor",
        "kpoints": [6, 6, 6],
        "nbands": 64,
        "notes": "Zincblende-like semiconductor example; verify the chosen Ga/As POTCAR family and gap treatment.",
    },
}

RUN_DEFAULTS = {
    "input_dir": "./inputs",
    "output_dir": "./stage1_demo",
    "material": "material",
    "prefix": "SiC",
    "expected_elements": [],
    "profile": "auto",
}

ENV_DEFAULTS = {
    "vasp_bin": "vasp_std",
    "oneapi_setup": "",
    "mpi_launcher": "mpirun",
    "mpi_cores": 4,
    "timeout_seconds": 3600,
    "conda_env": "",
}


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str | Path) -> dict:
    """Load config.yaml, merge the fixed parameter block, and return a dict."""
    path = Path(path)
    if not path.is_file():
        raise SystemExit(f"Config file does not exist: {path}")
    with path.open() as handle:
        raw = yaml.safe_load(handle) or {}
    config = {
        "parameters": _deep_merge(FIXED_PARAMETERS, raw.get("parameters") or {}),
        "run": _deep_merge(RUN_DEFAULTS, raw.get("run") or {}),
        "environment": _deep_merge(ENV_DEFAULTS, raw.get("environment") or {}),
    }
    return config


def canonical_profile(config: dict, elements: list[str] | None = None) -> dict | None:
    """选择 Si、SiC、GaAs 或 auto/unknown profile。"""
    requested = str(config["run"].get("profile", "auto")).lower().replace("-", "")
    if requested not in {"auto", "automatic"}:
        return MATERIAL_PROFILES.get(requested)
    material = str(config["run"].get("material", "")).lower().replace("-", "")
    if material in MATERIAL_PROFILES:
        return MATERIAL_PROFILES[material]
    if elements:
        target = set(elements)
        for profile in MATERIAL_PROFILES.values():
            if target == set(profile["elements"]):
                return profile
    return None


def _float_after(text: str, key: str) -> float | None:
    match = re.search(rf"{re.escape(key)}\s*=\s*([0-9.+Ee-]+)", text)
    return float(match.group(1)) if match else None


def read_potcar(path: Path) -> list[dict]:
    """读取每个赝势区块的名称、ENMAX 和 ZVAL。"""
    if not path.is_file():
        return []
    blocks: list[dict] = []
    current: dict | None = None
    for line in path.read_text(errors="replace").splitlines():
        if "TITEL" in line and "=" in line:
            if current:
                blocks.append(current)
            title = line.split("=", 1)[1].strip()
            token = title.split()[1] if len(title.split()) > 1 else ""
            element_match = re.match(r"([A-Z][a-z]?)", token)
            current = {"title": title, "element": element_match.group(1) if element_match else token}
        elif current is not None and "ENMAX" in line and "=" in line:
            current["enmax"] = _float_after(line, "ENMAX")
        elif current is not None and "ZVAL" in line and "=" in line:
            current["zval"] = _float_after(line, "ZVAL")
    if current:
        blocks.append(current)
    return blocks


def read_poscar(path: Path) -> dict:
    """读取 VASP4/VASP5 POSCAR 的元素名（如有）和原子数。"""
    lines = [line.strip() for line in path.read_text(errors="replace").splitlines() if line.strip()]
    if len(lines) < 7:
        raise ValueError(f"POSCAR 内容过短: {path}")
    tokens = lines[5].split()
    if all(re.fullmatch(r"[+-]?\d+", token) for token in tokens):
        names: list[str] = []
        counts = [int(token) for token in tokens]
    else:
        names = tokens
        counts = [int(token) for token in lines[6].split()]
    return {"elements": names, "counts": counts, "natoms": sum(counts)}


def read_kpoints(path: Path) -> dict:
    """读取 Gamma/Monkhorst 网格和偏移。"""
    lines = [line.strip() for line in path.read_text(errors="replace").splitlines() if line.strip()]
    if len(lines) < 4:
        raise ValueError(f"KPOINTS 内容过短: {path}")
    mode = lines[2].lower()
    grid = [int(x) for x in lines[3].split()[:3]]
    shift = [float(x) for x in lines[4].split()[:3]] if len(lines) >= 5 else [0.0, 0.0, 0.0]
    return {"mode": mode, "grid": grid, "shift": shift}


def inspect_inputs(config: dict) -> tuple[list[str], dict]:
    """检查输入文件，并返回阻断问题和可读的元数据。"""
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

    parameters = config["parameters"]
    requested_grid = parameters.get("kpoints")
    if requested_grid and kpoints["grid"] != list(requested_grid):
        problems.append(f"KPOINTS grid {kpoints['grid']} differs from configured grid {requested_grid}")
    requested_shift = parameters.get("kpoints_shift")
    if requested_shift and any(abs(a - b) > 1e-12 for a, b in zip(kpoints["shift"], requested_shift)):
        problems.append(f"KPOINTS shift {kpoints['shift']} differs from configured shift {requested_shift}")
    if kpoints["mode"] not in {"g", "gamma"}:
        problems.append(f"KPOINTS is not Gamma-centered: mode={kpoints['mode']}")

    enmax_values = [block.get("enmax") for block in potcar if block.get("enmax") is not None]
    max_enmax = max(enmax_values) if enmax_values else None
    encut = parameters.get("encut")
    if max_enmax is not None and encut is not None and float(encut) < max_enmax:
        problems.append(f"ENCUT={encut} is below max POTCAR ENMAX={max_enmax:.3f} eV")
    metadata = {
        "material": run.get("material", "material"),
        "potcar": potcar,
        "poscar": poscar,
        "kpoints": kpoints,
        "max_enmax": max_enmax,
    }
    profile = canonical_profile(config, pot_elements)
    metadata["profile"] = profile
    metadata["recommendations"] = []
    if profile:
        if pot_elements != profile["elements"]:
            metadata["recommendations"].append(
                f"Profile {profile['name']} expects POTCAR elements {profile['elements']}; actual order is {pot_elements}."
            )
        if list(parameters.get("kpoints") or []) != profile["kpoints"]:
            metadata["recommendations"].append(
                f"For {profile['name']}, the starting KPOINTS recommendation is {profile['kpoints']}; configured grid is {parameters.get('kpoints')}."
            )
        if int(parameters.get("nbands", 0)) != profile["nbands"]:
            metadata["recommendations"].append(
                f"For {profile['name']}, NBANDS={profile['nbands']} is only a starting value; configured NBANDS={parameters.get('nbands')}."
            )
        metadata["profile_summary"] = profile["notes"]
    else:
        metadata["profile_summary"] = (
            "Unknown material profile: use the generic checks, derive ENCUT from POTCAR ENMAX, "
            "choose KPOINTS from cell dimensions, and document convergence tests."
        )
    return problems, metadata


def validate_prepare(config: dict) -> list[str]:
    """Problems that must block the *prepare* step (output must be free)."""
    problems = []
    run = config["run"]
    input_problems, _ = inspect_inputs(config)
    problems.extend(input_problems)
    output_dir = Path(run["output_dir"])
    if output_dir.exists():
        problems.append(
            f"Output directory already exists (refusing to overwrite): {output_dir}"
        )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate paths only (input files present, output dir free)",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    if args.check:
        problems = validate_prepare(config)
        if problems:
            for message in problems:
                print(f"CONFIG=INVALID;{message}", file=sys.stderr)
            return 2
        print(f"CONFIG=VALID;OUTPUT={config['run']['output_dir']}")
        _, metadata = inspect_inputs(config)
        profile_name = metadata.get("profile", {}).get("name", "generic") if metadata.get("profile") else "generic"
        print(f"MATERIAL={metadata['material']};PROFILE={profile_name};POTCAR_ELEMENTS={[x['element'] for x in metadata['potcar']]};MAX_ENMAX={metadata['max_enmax']}")
        print(f"DECISION={metadata['profile_summary']}")
        for recommendation in metadata.get("recommendations", []):
            print(f"RECOMMENDATION={recommendation}")
        return 0

    p = config["parameters"]
    print(
        "CONFIG=OK;"
        f"ENCUT={p['encut']:g};NBANDS={p['nbands']};"
        f"CSHIFT={p['loptics']['cshift']:.3f};NEDOS={p['loptics']['nedos']};"
        f"KPOINTS={'x'.join(map(str, p['kpoints']))};"
        f"RESPONSE={p['response']}"
    )
    print(f"RUN={config['run']}")
    print(f"ENV={config['environment']}")
    problems, metadata = inspect_inputs(config)
    if problems:
        for message in problems:
            print(f"INPUT=INVALID;{message}", file=sys.stderr)
        return 2
    profile_name = metadata.get("profile", {}).get("name", "generic") if metadata.get("profile") else "generic"
    print(f"MATERIAL={metadata['material']};PROFILE={profile_name};POTCAR_ELEMENTS={[x['element'] for x in metadata['potcar']]};MAX_ENMAX={metadata['max_enmax']}")
    print(f"DECISION={metadata['profile_summary']}")
    for recommendation in metadata.get("recommendations", []):
        print(f"RECOMMENDATION={recommendation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
