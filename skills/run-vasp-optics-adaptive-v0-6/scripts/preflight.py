#!/usr/bin/env python3
"""Read-only environment, configuration, and input preflight for v0.6."""

from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import shutil
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_loader import load_config  # noqa: E402


POSTPROCESS_MODULES = ("yaml", "numpy", "pandas", "matplotlib")
INPUT_NAMES = ("POSCAR", "POTCAR", "KPOINTS")


def _find_executable(value: str) -> str | None:
    path = Path(str(value))
    if path.is_absolute() or path.parent != Path("."):
        if path.is_file() and (os.name == "nt" or path.stat().st_mode & stat.S_IXUSR):
            return str(path)
        return None
    return shutil.which(str(value))


def _check_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument(
        "--postprocess-only",
        action="store_true",
        help="skip Bash/MPI/VASP checks; useful on Windows for extract/plot/validate",
    )
    args = parser.parse_args()

    problems: list[str] = []
    try:
        config = load_config(args.config)
    except (OSError, SystemExit, ValueError) as exc:
        print(f"PREFLIGHT=FAIL;CONFIG={exc}", file=sys.stderr)
        return 2

    if platform.system() == "Windows" and not args.postprocess_only:
        problems.append("Native Windows cannot run run.py; use WSL or a remote Linux host")

    for module in POSTPROCESS_MODULES:
        if not _check_module(module):
            problems.append(f"Missing Python module: {module}")

    run = config["run"]
    input_dir = Path(run["input_dir"])
    for name in INPUT_NAMES:
        path = input_dir / name
        if not path.is_file() or path.stat().st_size == 0:
            problems.append(f"Missing or empty input file: {path}")

    postprocess = config.get("postprocess", {})
    try:
        constant = float(postprocess["wavelength_constant_nm_eV"])
        xmin = float(postprocess["plot_min_nm"])
        xmax = float(postprocess["plot_max_nm"])
        if constant <= 0 or xmin < 0 or xmax <= xmin:
            problems.append("Invalid postprocess wavelength constant or plot bounds")
    except (KeyError, TypeError, ValueError):
        problems.append("postprocess wavelength values must be numeric")

    parameters = config.get("parameters", {})
    if parameters.get("response", "density-density") != "density-density":
        problems.append("parameters.response must be density-density in adaptive-v0.6")
    try:
        mpi_cores = int(config["environment"].get("mpi_cores", 4))
        timeout_seconds = int(config["environment"].get("timeout_seconds", 3600))
        if mpi_cores < 1:
            problems.append("environment.mpi_cores must be a positive integer")
        if timeout_seconds < 1:
            problems.append("environment.timeout_seconds must be a positive integer")
    except (TypeError, ValueError):
        problems.append("environment.mpi_cores and timeout_seconds must be integers")

    raw_nbands = config.get("_raw_parameters", {}).get("nbands")
    metadata = config.get("_metadata", {})
    occupied = ((metadata.get("recommendation") or {}).get("values") or {}).get(
        "occupied_bands_estimate"
    )
    if isinstance(raw_nbands, (int, float)) and occupied is not None:
        if int(raw_nbands) < int(occupied):
            problems.append(
                f"parameters.nbands={raw_nbands} is below estimated occupied bands={occupied}"
            )

    if not args.postprocess_only:
        env = config["environment"]
        for key in ("vasp_bin", "mpi_launcher"):
            if not _find_executable(str(env.get(key, ""))):
                problems.append(f"Executable not found: environment.{key}={env.get(key)!r}")
        if shutil.which("bash") is None:
            problems.append("Executable not found: bash")
        if shutil.which("timeout") is None:
            problems.append("Executable not found: timeout (GNU coreutils)")
        setup = str(env.get("oneapi_setup", "") or "")
        if setup.startswith("<") and setup.endswith(">"):
            problems.append("environment.oneapi_setup still contains a placeholder")
        elif setup and not Path(setup).is_file():
            problems.append(f"oneAPI setup script does not exist: {setup}")

    if problems:
        for problem in problems:
            print(f"PREFLIGHT=FAIL;{problem}", file=sys.stderr)
        return 2

    mode = "postprocess-only" if args.postprocess_only else "full"
    print(
        f"PREFLIGHT=PASS;MODE={mode};PLATFORM={platform.system()};"
        f"PYTHON={sys.executable};INPUT_DIR={input_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
