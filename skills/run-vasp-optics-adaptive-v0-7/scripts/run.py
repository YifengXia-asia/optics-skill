#!/usr/bin/env python3
"""Run the two-gate DFT -> classify -> LOPTICS workflow (adaptive v0.7).

The first invocation can stop successfully after ground-state classification.
After the user reviews system_classification.json and confirms the applicable
non-bulk/metal policy, rerun the same command to start LOPTICS.
"""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify_electronic import classify_ground_state, write_report  # noqa: E402
from config_loader import inspect_inputs, load_config  # noqa: E402
from prepare import write_incar_loptics  # noqa: E402


def _bash(command: str) -> int:
    return subprocess.run(["bash", "-c", command]).returncode


def selected_vasp_bin(config: dict) -> str:
    env = config["environment"]
    grid = ((config.get("_metadata") or {}).get("kpoints") or {}).get("grid") or []
    gamma_only = len(grid) == 3 and all(int(value) == 1 for value in grid)
    gamma_bin = str(env.get("vasp_gamma_bin", "") or "")
    if gamma_only and bool(env.get("auto_select_gamma", True)) and gamma_bin:
        return gamma_bin
    return str(env.get("vasp_bin", "vasp_std"))


def run_vasp(directory: Path, stdout_name: str, config: dict) -> int:
    env = config["environment"]
    parts = []
    setup = str(env.get("oneapi_setup", "") or "")
    if setup:
        parts.append(f"test -f {shlex.quote(setup)}")
        parts.append(f"source {shlex.quote(setup)} >/dev/null 2>&1")
    parts.append(f"cd {shlex.quote(str(directory))}")
    launcher = shlex.quote(str(env.get("mpi_launcher", "mpirun")))
    parts.append(
        "timeout {timeout}s {launcher} -np {cores} {vasp} < /dev/null > {out} 2>&1".format(
            timeout=int(env.get("timeout_seconds", 3600)),
            cores=int(env.get("mpi_cores", 4)),
            vasp=shlex.quote(selected_vasp_bin(config)),
            launcher=launcher,
            out=shlex.quote(stdout_name),
        )
    )
    return _bash(" && ".join(parts))


def check_runtime(config: dict) -> list[str]:
    env = config["environment"]
    problems = []
    vasp = Path(selected_vasp_bin(config))
    if vasp.is_absolute() and (not vasp.is_file() or not vasp.stat().st_mode & 0o111):
        problems.append(f"VASP executable is missing or not executable: {vasp}")
    setup = str(env.get("oneapi_setup", "") or "")
    if setup and not Path(setup).is_file():
        problems.append(f"oneAPI setup script does not exist: {setup}")
    if not env.get("mpi_launcher"):
        problems.append("mpi_launcher is empty")
    return problems


def check_nonempty(directory: Path, names) -> list[str]:
    return [
        str(directory / name) for name in names
        if not (directory / name).is_file() or (directory / name).stat().st_size == 0
    ]


def _complete_dft(directory: Path) -> bool:
    return not check_nonempty(directory, ("OUTCAR", "vasprun.xml", "WAVECAR", "CHGCAR"))


def _load_or_classify(config: dict, dft: Path, report_path: Path) -> dict:
    if report_path.is_file():
        return json.loads(report_path.read_text(encoding="utf-8"))
    report = classify_ground_state(config, dft / "vasprun.xml")
    write_report(report, report_path)
    return report


def _decision_problems(config: dict, report: dict) -> list[str]:
    run = config["run"]
    problems = []
    if not bool(run.get("confirm_electronic_classification", False)):
        problems.append(
            "Review system_classification.json, then set run.confirm_electronic_classification: true"
        )
    structure = report.get("structure_class")
    if structure != "bulk-3d-candidate" and not bool(run.get("allow_nonbulk_supercell_optics", False)):
        problems.append(
            "Non-bulk candidate requires run.allow_nonbulk_supercell_optics: true; outputs remain supercell-volume dependent"
        )
    if report.get("electronic_class") == "metal-or-semimetal":
        mode = str(run.get("metal_optics_mode", "stop"))
        if mode == "stop":
            problems.append(
                "Metal/semimetal detected: choose run.metal_optics_mode=interband-only or drude"
            )
        elif mode == "drude" and float(config["parameters"]["loptics"].get("wplasmai", 0.0)) <= 0:
            problems.append("Drude mode requires parameters.loptics.wplasmai > 0 eV")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--stage", choices=("auto", "dft", "loptics"), default="auto")
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
    report_path = output_dir / "system_classification.json"
    for directory in (dft, optics):
        if not directory.is_dir():
            print(f"RUN=FAIL;missing prepared directory: {directory}", file=sys.stderr)
            return 2

    dft_outputs = [dft / name for name in ("OUTCAR", "vasprun.xml", "WAVECAR", "CHGCAR")]
    if any(path.exists() for path in dft_outputs) and not _complete_dft(dft):
        print("RUN=FAIL;partial ground-state outputs exist; use a new output_dir", file=sys.stderr)
        return 2

    dft_was_complete = _complete_dft(dft)
    if not dft_was_complete:
        if args.stage == "loptics":
            print("RUN=FAIL;ground state has not been completed", file=sys.stderr)
            return 2
        if run_vasp(dft, "DFT.stdout", config) != 0:
            print("RUN=FAIL;DFT VASP step returned a nonzero exit status", file=sys.stderr)
            return 1
        missing = check_nonempty(dft, ("OUTCAR", "vasprun.xml", "WAVECAR", "CHGCAR"))
        if missing:
            print(f"RUN=FAIL;DFT missing outputs: {missing}", file=sys.stderr)
            return 1
        if "General timing and accounting" not in (dft / "OUTCAR").read_text(errors="replace"):
            print("RUN=FAIL;DFT OUTCAR has no final timing block", file=sys.stderr)
            return 1
        report = _load_or_classify(config, dft, report_path)
        print(
            f"DFT=PASS;STRUCTURE_CLASS={report['structure_class']};"
            f"ELECTRONIC_CLASS={report['electronic_class']};"
            f"GAP_EV={report.get('estimated_gap_eV')};REPORT={report_path}"
        )
        if args.stage == "dft" or not bool(run.get("confirm_electronic_classification", False)):
            print("RUN=PAUSED;REASON=electronic classification requires review before LOPTICS")
            return 0

    if dft_was_complete:
        source = "reused-existing-dft" if str(run.get("existing_dft_dir", "") or "").strip() else "prepared-dft"
        completed_report = _load_or_classify(config, dft, report_path)
        print(
            f"DFT=PASS;SOURCE={source};STRUCTURE_CLASS={completed_report['structure_class']};"
            f"ELECTRONIC_CLASS={completed_report['electronic_class']};"
            f"GAP_EV={completed_report.get('estimated_gap_eV')};REPORT={report_path}"
        )

    report = _load_or_classify(config, dft, report_path)
    decision_problems = _decision_problems(config, report)
    if decision_problems:
        for message in decision_problems:
            print(f"RUN=PAUSED;{message}")
        return 0
    if args.stage == "dft":
        print("RUN=PAUSED;REASON=--stage dft requested")
        return 0

    existing_optics = [optics / name for name in ("OUTCAR", "vasprun.xml", "WAVEDER")]
    if any(path.exists() for path in existing_optics):
        print(f"RUN=FAIL;refusing to overwrite existing LOPTICS outputs: {existing_optics}", file=sys.stderr)
        return 2

    for name in ("POSCAR", "POTCAR", "KPOINTS", "WAVECAR", "CHGCAR"):
        source = dft / name
        if not source.is_file():
            print(f"RUN=FAIL;cannot copy missing DFT file: {source}", file=sys.stderr)
            return 1
        shutil.copy2(source, optics / name)

    _, metadata = inspect_inputs(config)
    write_incar_loptics(
        optics,
        config["parameters"],
        str(run.get("material", "material")),
        metadata,
        electronic_class=str(report.get("electronic_class")),
        metal_mode=str(run.get("metal_optics_mode", "stop")),
    )
    shutil.copy2(report_path, optics / "system_classification.json")

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

    print(
        f"RUN=PASS;OUTPUT={output_dir};STRUCTURE_CLASS={report['structure_class']};"
        f"ELECTRONIC_CLASS={report['electronic_class']};"
        f"METAL_MODE={run.get('metal_optics_mode', 'stop')};VASP_SELECTED={selected_vasp_bin(config)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
