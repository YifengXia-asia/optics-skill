#!/usr/bin/env python3
"""Prepare a non-destructive, type-adaptive DFT/LOPTICS run directory (v0.7).

Keep the supplied KPOINTS, use resolved reviewable parameters, carry selected
user INCAR physics tags forward when present, and refuse to overwrite an
existing output directory. run.py refreshes the final LOPTICS INCAR only
after the ground-state electronic classification is confirmed.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_loader import inspect_inputs, load_config, validate_prepare  # noqa: E402


INHERITED_PHYSICS_KEYS = (
    "GGA", "METAGGA", "LASPH", "ADDGRID", "IVDW", "LMAXMIX",
    "LDAU", "LDAUTYPE", "LDAUL", "LDAUU", "LDAUJ",
    "ISPIN", "MAGMOM", "LSORBIT", "LNONCOLLINEAR", "SAXIS",
)


def _flag(value) -> str:
    return ".TRUE." if value else ".FALSE."


def _sci(value: float) -> str:
    mantissa, exponent = f"{value:.0E}".split("E")
    return f"{mantissa}E{int(exponent)}"


def _inherited_lines(metadata: dict, policy: str) -> list[str]:
    if policy != "preserve-user":
        return []
    incar = metadata.get("input_incar") or {}
    return [f"{key:<8}= {incar[key]}" for key in INHERITED_PHYSICS_KEYS if key in incar]


def write_incar_dft(directory: Path, p: dict, material: str, metadata: dict | None = None) -> None:
    d = p["dft"]
    inherited = _inherited_lines(metadata or {}, str(p.get("parameter_policy", "preserve-user")))
    lines = [
        f"SYSTEM  = {material} ground-state classification",
        *inherited,
        f"ENCUT   = {p['encut']:g}",
        "PREC    = Accurate",
        f"ALGO    = {d['algo']}",
        f"NBANDS  = {p['nbands']}",
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
    (directory / "INCAR").write_text("\n".join(lines), encoding="utf-8")


def write_incar_loptics(
    directory: Path,
    p: dict,
    material: str,
    metadata: dict | None = None,
    electronic_class: str | None = None,
    metal_mode: str = "stop",
) -> None:
    o = p["loptics"]
    inherited = _inherited_lines(metadata or {}, str(p.get("parameter_policy", "preserve-user")))
    extra: list[str] = []
    if electronic_class == "metal-or-semimetal" and metal_mode == "drude":
        extra.append(f"WPLASMAI = {float(o.get('wplasmai', 0.0)):.6g}")
    lines = [
        f"SYSTEM  = {material} independent-particle optics",
        *inherited,
        f"ENCUT   = {p['encut']:g}",
        "PREC    = Accurate",
        f"ISTART  = {o['istart']}",
        f"ICHARG  = {o['icharg']}",
        f"ALGO    = {o['algo']}",
        f"NBANDS  = {p['nbands']}",
        f"LOPTICS = {_flag(o['loptics'])}",
        f"CSHIFT  = {float(o['cshift']):.3f}",
        *extra,
        f"NEDOS   = {o['nedos']}",
        f"EDIFF   = {_sci(float(o['ediff']))}",
        f"ISMEAR  = {o['ismear']}",
        f"SIGMA   = {o['sigma']}",
        f"ISPIN   = {o['ispin']}",
        f"LWAVE   = {_flag(o['lwave'])}",
        f"LCHARG  = {_flag(o['lcharg'])}",
        "",
    ]
    (directory / "INCAR").write_text("\n".join(lines), encoding="utf-8")


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
    _, metadata = inspect_inputs(config)
    preliminary = metadata.get("classification", {}).get("electronic_character")
    existing_raw = str(run.get("existing_dft_dir", "") or "").strip()
    existing_dft = Path(existing_raw) if existing_raw else None
    if existing_dft is None:
        write_incar_dft(dft, parameters, material, metadata)
    else:
        if (existing_dft / "INCAR").is_file():
            shutil.copy2(existing_dft / "INCAR", dft / "INCAR")
        else:
            write_incar_dft(dft, parameters, material, metadata)
        for name in ("OUTCAR", "vasprun.xml", "WAVECAR", "CHGCAR"):
            shutil.copy2(existing_dft / name, dft / name)
    write_incar_loptics(
        optics,
        parameters,
        material,
        metadata,
        electronic_class=preliminary,
        metal_mode=str(run.get("metal_optics_mode", "stop")),
    )

    print(
        f"MATERIAL={material};POTCAR_ELEMENTS="
        f"{[x['element'] for x in metadata.get('potcar', [])]};"
        f"MAX_ENMAX={metadata.get('max_enmax')};STRUCTURE_CLASS="
        f"{metadata.get('classification', {}).get('structure_class')}"
    )
    print(f"INHERITED_INCAR_KEYS={sorted(metadata.get('input_incar', {}))}")
    print(f"PREPARE=OK;OUTPUT={output_dir}")
    if existing_dft is not None:
        print(f"DFT_SOURCE=REUSED_COPY;SOURCE={existing_dft};SOURCE_MODIFIED=false")
    print(f"DFT_INCAR={dft / 'INCAR'}")
    print(f"LOPTICS_INCAR_PRELIMINARY={optics / 'INCAR'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
