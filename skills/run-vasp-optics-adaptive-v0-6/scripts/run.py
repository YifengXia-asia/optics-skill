#!/usr/bin/env python3
"""Run the prepared, material-aware DFT and LOPTICS steps (adaptive-v0.6).

Mirrors the template runner (scripts/run_vasp_stage1.sh): source oneAPI
when configured, run 00_DFT and stop on a nonzero exit code, require
non-empty OUTCAR/WAVECAR/CHGCAR with a final timing block, copy
POSCAR/POTCAR/KPOINTS/WAVECAR/CHGCAR into 01_LOPTICS, run the LOPTICS
step, then require non-empty OUTCAR/vasprun.xml/WAVECAR/WAVEDER plus
real and imaginary frequency-dependent dielectric sections and a final
timing block.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_loader import load_config  # noqa: E402


def _bash(cmd: str) -> int:
    return subprocess.run(["bash", "-c", cmd]).returncode


def run_vasp(directory: Path, stdout_name: str, config: dict) -> int:
    env = config["environment"]
    parts = []
    setup = env.get("oneapi_setup")
    if setup:
        parts.append(f"test -f {shlex.quote(str(setup))}")
        parts.append(f"source {shlex.quote(str(setup))} >/dev/null 2>&1")
    parts.append(f"cd {shlex.quote(str(directory))}")
    launcher = shlex.quote(str(env.get("mpi_launcher", "mpirun")))
    parts.append(
        "timeout {timeout}s {launcher} -np {cores} {vasp} < /dev/null > {out} 2>&1".format(
            timeout=int(env.get("timeout_seconds", 3600)),
            cores=int(env.get("mpi_cores", 4)),
            vasp=shlex.quote(env.get("vasp_bin", "vasp_std")),
            launcher=launcher,
            out=shlex.quote(stdout_name),
        )
    )
    return _bash(" && ".join(parts))


def check_runtime(config: dict) -> list[str]:
    """检查 VASP、MPI 和 oneAPI 配置，避免静默失败。"""
    env = config["environment"]
    problems = []
    vasp = Path(str(env.get("vasp_bin", "vasp_std")))
    if vasp.is_absolute():
        if not vasp.is_file() or not vasp.stat().st_mode & 0o111:
            problems.append(f"VASP executable is missing or not executable: {vasp}")
    if env.get("oneapi_setup") and not Path(str(env["oneapi_setup"])).is_file():
        problems.append(f"oneAPI setup script does not exist: {env['oneapi_setup']}")
    if not env.get("mpi_launcher"):
        problems.append("mpi_launcher is empty")
    return problems


def check_nonempty(directory: Path, names) -> list[str]:
    missing = []
    for name in names:
        path = directory / name
        if not path.is_file() or path.stat().st_size == 0:
            missing.append(str(path))
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    runtime_problems = check_runtime(config)
    if runtime_problems:
        for message in runtime_problems:
            print(f"RUN=FAIL;{message}", file=sys.stderr)
        return 2
    run = config["run"]
    output_dir = Path(run["output_dir"])
    dft = output_dir / "00_DFT"
    optics = output_dir / "01_LOPTICS"

    for directory in (dft, optics):
        if not directory.is_dir():
            print(f"RUN=FAIL;missing prepared directory: {directory}", file=sys.stderr)
            return 2

    # Never overwrite the output of an earlier run when the runner is called directly.
    existing = [
        path for directory, names in ((dft, ("OUTCAR", "WAVECAR", "CHGCAR")),
                                      (optics, ("OUTCAR", "vasprun.xml", "WAVEDER")))
        for path in (directory / name for name in names)
        if path.exists()
    ]
    if existing:
        print(f"RUN=FAIL;refusing to overwrite existing outputs: {existing}", file=sys.stderr)
        return 2

    # --- Ground-state DFT -------------------------------------------------
    if run_vasp(dft, "DFT.stdout", config) != 0:
        print("RUN=FAIL;DFT VASP step returned a nonzero exit status", file=sys.stderr)
        return 1
    missing = check_nonempty(dft, ("OUTCAR", "WAVECAR", "CHGCAR"))
    if missing:
        print(f"RUN=FAIL;DFT missing outputs: {missing}", file=sys.stderr)
        return 1
    if "General timing and accounting" not in (dft / "OUTCAR").read_text(errors="replace"):
        print("RUN=FAIL;DFT OUTCAR has no final timing block", file=sys.stderr)
        return 1

    # --- Handoff ----------------------------------------------------------
    for name in ("POSCAR", "POTCAR", "KPOINTS", "WAVECAR", "CHGCAR"):
        source = dft / name
        if not source.is_file():
            print(f"RUN=FAIL;cannot copy missing DFT output: {source}", file=sys.stderr)
            return 1
        (optics / name).write_bytes(source.read_bytes())

    # --- LOPTICS ----------------------------------------------------------
    if run_vasp(optics, "LOPTICS.stdout", config) != 0:
        print("RUN=FAIL;LOPTICS VASP step returned a nonzero exit status", file=sys.stderr)
        return 1
    missing = check_nonempty(optics, ("OUTCAR", "vasprun.xml", "WAVECAR", "WAVEDER"))
    if missing:
        print(f"RUN=FAIL;LOPTICS missing outputs: {missing}", file=sys.stderr)
        return 1
    outcar = (optics / "OUTCAR").read_text(errors="replace")
    if "frequency dependent IMAGINARY DIELECTRIC FUNCTION" not in outcar:
        print("RUN=FAIL;LOPTICS OUTCAR has no imaginary dielectric function", file=sys.stderr)
        return 1
    if "frequency dependent      REAL DIELECTRIC FUNCTION" not in outcar:
        print("RUN=FAIL;LOPTICS OUTCAR has no real dielectric function", file=sys.stderr)
        return 1
    if "General timing and accounting" not in outcar:
        print("RUN=FAIL;LOPTICS OUTCAR has no final timing block", file=sys.stderr)
        return 1

    print(f"RUN=PASS;OUTPUT={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
