#!/usr/bin/env python3
"""Prepare a non-destructive, material-aware DFT/LOPTICS run directory (mc-v0.2).

Reads the fixed parameter block from config.yaml via scripts/config_loader.py,
creates <output_dir>/00_DFT and <output_dir>/01_LOPTICS, copies
POSCAR/POTCAR/KPOINTS, and writes explicit INCAR files with the fixed
stage-1 parameters (ENCUT=414, NBANDS=64, CSHIFT=0.100, NEDOS=2000,
ALGO Normal/Exact, EDIFF 1E-6/1E-8, ISTART=1, ICHARG=11). Refuses to
overwrite an existing output directory.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_loader import load_config, validate_prepare, inspect_inputs  # noqa: E402


def _flag(value) -> str:
    return ".TRUE." if value else ".FALSE."


def _sci(value: float) -> str:
    """Format 1e-6 -> '1E-6' exactly like the validated template INCAR."""
    mantissa, exponent = f"{value:.0E}".split("E")
    return f"{mantissa}E{int(exponent)}"


def write_incar_dft(directory: Path, p: dict, material: str) -> None:
    d = p["dft"]
    (directory / "INCAR").write_text(
        "\n".join(
            [
                f"SYSTEM  = {material} stage1 ground state",
                f"ENCUT   = {p['encut']:g}",
                "PREC    = Accurate",
                f"ALGO    = {d['algo']}",
                f"EDIFF   = {_sci(float(d['ediff']))}",
                f"ISMEAR  = {d['ismear']}",
                f"SIGMA   = {d['sigma']}",
                f"ISPIN   = {d['ispin']}",
                f"IBRION  = {d['ibrion']}",
                f"NSW     = {d['nsw']}",
                f"LWAVE   = {_flag(d['lwave'])}",
                f"LCHARG  = {_flag(d['lcharg'])}",
                "",
            ]
        )
    )


def write_incar_loptics(directory: Path, p: dict, material: str) -> None:
    o = p["loptics"]
    (directory / "INCAR").write_text(
        "\n".join(
            [
                f"SYSTEM  = {material} stage1 independent-particle optics",
                f"ENCUT   = {p['encut']:g}",
                "PREC    = Accurate",
                f"ISTART  = {o['istart']}",
                f"ICHARG  = {o['icharg']}",
                f"ALGO    = {o['algo']}",
                f"NBANDS  = {p['nbands']}",
                f"LOPTICS = {_flag(o['loptics'])}",
                f"CSHIFT  = {o['cshift']:.3f}",
                f"NEDOS   = {o['nedos']}",
                f"EDIFF   = {_sci(float(o['ediff']))}",
                f"ISMEAR  = {o['ismear']}",
                f"SIGMA   = {o['sigma']}",
                f"ISPIN   = {o['ispin']}",
                f"LWAVE   = {_flag(o['lwave'])}",
                f"LCHARG  = {_flag(o['lcharg'])}",
                "",
            ]
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    args = parser.parse_args()

    config = load_config(args.config)
    problems = validate_prepare(config)
    if problems:
        for message in problems:
            print(f"PREPARE=FAIL;{message}", file=sys.stderr)
        return 2

    run = config["run"]
    parameters = config["parameters"]
    output_dir = Path(run["output_dir"])
    input_dir = Path(run["input_dir"])
    dft = output_dir / "00_DFT"
    optics = output_dir / "01_LOPTICS"
    dft.mkdir(parents=True)
    optics.mkdir()
    for name in ("POSCAR", "POTCAR", "KPOINTS"):
        shutil.copy2(input_dir / name, dft / name)
        shutil.copy2(input_dir / name, optics / name)

    material = str(run.get("material", "material"))
    write_incar_dft(dft, parameters, material)
    write_incar_loptics(optics, parameters, material)

    _, metadata = inspect_inputs(config)
    print(f"MATERIAL={material};POTCAR_ELEMENTS={[x['element'] for x in metadata.get('potcar', [])]};MAX_ENMAX={metadata.get('max_enmax')}")

    print(f"PREPARE=OK;OUTPUT={output_dir}")
    print(f"DFT_INCAR={dft / 'INCAR'}")
    print(f"LOPTICS_INCAR={optics / 'INCAR'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
