---
name: vasp-sic-optics-stage1-mc-v0-2
description: "Use when the user wants a configurable VASP independent-particle optical workflow for a small insulating material: validate POSCAR/POTCAR/KPOINTS, run DFT then LOPTICS, extract epsilon1/epsilon2/n/k/alpha/reflectivity, and produce energy- and wavelength-domain CSV/PNG outputs. Defaults are the SiC demo, but material name, prefix, ENCUT, NBANDS, KPOINTS, and paths are user-configurable after checks. Do not use for GW, BSE, CHI/RPA, local-field, phonon/ionic dielectric, SOC, spin/magnetic, metallic, or structural-relaxation workflows."
---

# VASP 独立粒子光学流程 v0.2

## Overview

This skill is a configurable workflow for a small insulating material:

`POSCAR/POTCAR/KPOINTS → DFT → WAVECAR/CHGCAR → LOPTICS → vasprun.xml → ε1/ε2 → n/k/α/R → energy and wavelength CSV/PNG → validation`

The default profile reproduces the SiC demo (`ENCUT=414`, `6×6×6 Gamma`,
`NBANDS=64`, `CSHIFT=0.100`, `NEDOS=2000`). These are defaults, not universal
constants. v0.2 allows a user to change material, prefix, POTCAR, ENCUT,
NBANDS, KPOINTS, MPI resources, and paths while checking the actual inputs.

## When to Use

Use this skill for a non-metallic or insulating material when the requested
workflow is ground-state DFT followed by VASP `LOPTICS`, then energy/wavelength
post-processing of `epsilon1`, `epsilon2`, `n`, `k`, `alpha (cm^-1)`, and normal-
incidence reflectivity `R`.

Do not use it for GW/BSE, `ALGO=CHI`, RPA/local-field studies, phonon or ionic
dielectric response, SOC, spin/magnetic workflows, metals, relaxation, or a
generic high-throughput material router. Stop and propose a separate profile.

## Prerequisites

1. A working `vasp_std`, MPI launcher, and (when required) oneAPI setup script.
2. A post-processing Python environment containing PyYAML, NumPy, pandas,
   matplotlib, and lxml.
3. A new input directory containing `POSCAR`, `POTCAR`, and `KPOINTS`.
4. `POTCAR` blocks must be in the same element order as POSCAR. The loader
   reads `TITEL`, `ENMAX`, and `ZVAL` and reports the actual pseudopotentials.
5. `KPOINTS` must be Gamma-centered and match the configured grid/shift.
6. Work in a new output directory. Existing VASP outputs are never overwritten.

Check inputs before preparing:

```bash
python <skill-path>/scripts/config_loader.py --config config.yaml --check
```

If input validation fails, stop and fix the named POSCAR/POTCAR/KPOINTS issue.

## Configuration and parameter policy

Copy `config.yaml.example` to `config.yaml`. Change `run.material` and
`run.prefix` when changing materials. The prefix controls filenames only; it
does not change physics.

The SiC demo defaults are:

| Parameter | DFT | LOPTICS | Meaning |
|---|---:|---:|---|
| `ENCUT` | 414 eV | 414 eV | Set at or above the largest POTCAR `ENMAX`; test convergence |
| `KPOINTS` | 6×6×6 Gamma | same | Brillouin-zone sampling; change for cell size and convergence |
| `EDIFF` | 1E-6 | 1E-8 | Electronic convergence |
| `NBANDS` | 64 | 64 | Empty-band range; increase for higher photon energies |
| `ALGO` | Normal | Exact | DFT and optical electronic algorithms |
| `LOPTICS` | off | true | Interband independent-particle response |
| `CSHIFT` | — | 0.100 eV | Spectral broadening |
| `NEDOS` | — | 2000 | Frequency-grid resolution |
| `ISTART/ICHARG` | — | 1/11 | Reuse DFT WAVECAR/CHGCAR |

The program does not reject a different material or parameter value merely
because it differs from the SiC defaults. It does reject a missing input,
wrong POSCAR/POTCAR order, non-Gamma KPOINTS, or ENCUT below the actual POTCAR
maximum when configured to do so.

## Workflow

### 1. Validate inputs

```bash
python <skill-path>/scripts/config_loader.py --config config.yaml --check
```

The output reports material, POTCAR element order, each pseudopotential's
`ENMAX`/`ZVAL`, the largest `ENMAX`, and the KPOINTS grid.

### 2. Prepare a new run

```bash
python <skill-path>/scripts/prepare.py --config config.yaml
```

This creates `00_DFT/` and `01_LOPTICS/`, copies POSCAR/POTCAR/KPOINTS, and
writes material-labelled INCAR files. It refuses an existing output directory.

### 3. Run DFT and LOPTICS

```bash
python <skill-path>/scripts/run.py --config config.yaml
```

The runner checks VASP/MPI/oneAPI, refuses existing output files, runs DFT,
checks `OUTCAR`, `WAVECAR`, and `CHGCAR`, copies the handoff files, then runs
LOPTICS. It requires `OUTCAR`, `vasprun.xml`, `WAVECAR`, `WAVEDER`, both
frequency-dependent dielectric-function sections, and a final timing block.

### 4. Extract energy-domain quantities

```bash
python <skill-path>/scripts/extract.py --config config.yaml
```

The script reads the configured dielectric response, computes the six quantities,
and writes `<prefix>_optical_properties.csv` plus six energy-domain PNGs.
`alpha_cm-1` is an absorption coefficient, not a thickness-dependent absorption
percentage.

### 5. Produce wavelength-domain quantities

```bash
python <skill-path>/scripts/plot.py --config config.yaml
```

It uses `lambda_nm = 1239.841984 / energy_eV`, drops the zero-energy row, sorts
by wavelength, and writes a wavelength CSV plus six wavelength plots. It also
writes absorption and reflectivity views over the configured wavelength window.
Thus `alpha(lambda)` and `R(lambda)` are explicit outputs.

### 6. Validate without changing results

```bash
python <skill-path>/scripts/validate.py --config config.yaml
```

The validator is read-only. It checks VASP files, dielectric sections, the
selected response, CSV columns, finite values, monotonic energy/wavelength,
`n/k/alpha >= 0`, `0 <= R <= 1`, and all required plots. Success prints
`VALIDATION=PASS`.

## Common Pitfalls

1. **No POTCAR or wrong order** — VASP cannot run correctly. Rebuild POTCAR
   from the chosen pseudopotential blocks in POSCAR order; do not hand-edit it.
2. **ENCUT below POTCAR ENMAX** — raise ENCUT or document a deliberate test.
3. **KPOINTS copied from another material** — choose a grid appropriate to the
   cell and update the configuration before preparation.
4. **oneAPI/MPI unavailable** — stop and fix the environment; do not ignore a
   failed setup script.
5. **LOPTICS handoff mismatch** — keep POSCAR, POTCAR, KPOINTS, spin settings,
   and NBANDS compatible between DFT and LOPTICS.
6. **`alpha` mistaken for absorption percentage** — alpha is in `cm^-1`; a
   sample thickness and optical geometry are needed for absorption fraction.
7. **Visible-range plot looks flat** — inspect log-y and the full UV range before
   calling it a failure.

## Verification Checklist

- [ ] `POSCAR`, `POTCAR`, and `KPOINTS` exist.
- [ ] POSCAR/POTCAR element order and counts match.
- [ ] POTCAR `TITEL`, `ENMAX`, and `ZVAL` were recorded.
- [ ] KPOINTS is Gamma-centered and matches the configured grid/shift.
- [ ] ENCUT is at least the largest POTCAR ENMAX unless a deliberate test is documented.
- [ ] DFT has non-empty `OUTCAR`, `WAVECAR`, and `CHGCAR`.
- [ ] LOPTICS has non-empty `OUTCAR`, `vasprun.xml`, `WAVECAR`, and `WAVEDER`.
- [ ] OUTCAR contains real and imaginary frequency-dependent dielectric functions.
- [ ] Energy and wavelength CSVs contain epsilon1/epsilon2/n/k/alpha/R.
- [ ] `alpha(lambda)` and `R(lambda)` plots exist.
- [ ] `n`, `k`, and `alpha` are non-negative; `R` is in [0, 1].
- [ ] `validate.py` prints `VALIDATION=PASS`.
- [ ] Results are labelled independent-particle LOPTICS; no GW/BSE/phonon claim is made.
