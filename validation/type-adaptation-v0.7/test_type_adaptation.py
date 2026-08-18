from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "run-vasp-optics-adaptive-v0-7" / "scripts"


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


config_loader = load_module("config_loader")
classify_electronic = load_module("classify_electronic")


POTCAR = """TITEL  = PAW_PBE C 08Apr2002
ZVAL   = 4.000
ENMAX  = 400.000; ENMIN = 300.000
End of Dataset
"""


def poscar(vectors, positions):
    return "\n".join([
        "C test", "1.0",
        *[" ".join(map(str, vector)) for vector in vectors],
        "C", str(len(positions)), "Direct",
        *[" ".join(map(str, position)) for position in positions], "",
    ])


def kpoints(grid):
    return "\n".join(["mesh", "0", "Gamma", " ".join(map(str, grid)), "0 0 0", ""])


def eigen_xml(rows_by_kpoint, efermi=0.0):
    sets = []
    for index, rows in enumerate(rows_by_kpoint, start=1):
        body = "".join(f"<r>{energy} {occupation}</r>" for energy, occupation in rows)
        sets.append(f'<set comment="kpoint {index}">{body}</set>')
    return (
        "<modeling><calculation><dos><i name=\"efermi\">"
        f"{efermi}</i></dos><eigenvalues><array><set><set comment=\"spin 1\">"
        + "".join(sets)
        + "</set></set></array></eigenvalues></calculation></modeling>"
    )


class TypeAdaptationTests(unittest.TestCase):
    def make_case(self, base: Path, vectors, grid, positions=((0, 0, 0),), incar="", config_overrides=None):
        input_dir = base / "inputs"
        input_dir.mkdir()
        (input_dir / "POSCAR").write_text(poscar(vectors, positions), encoding="utf-8")
        (input_dir / "POTCAR").write_text(POTCAR, encoding="utf-8")
        (input_dir / "KPOINTS").write_text(kpoints(grid), encoding="utf-8")
        if incar:
            (input_dir / "INCAR").write_text(incar, encoding="utf-8")
        config_path = base / "config.yaml"
        raw_config = {
            "run": {"input_dir": str(input_dir), "output_dir": str(base / "out")},
            "parameters": {"kpoints": "auto", "encut": "auto"},
        }
        raw_config = config_loader._deep_merge(raw_config, config_overrides or {})
        config_path.write_text(yaml.safe_dump(raw_config), encoding="utf-8")
        return config_loader.load_config(config_path)

    def test_structure_classes_and_user_kpoints(self):
        cases = [
            ([[4, 0, 0], [0, 4, 0], [0, 0, 4]], [6, 6, 6], "bulk-3d-candidate"),
            ([[2.46, 0, 0], [0, 2.46, 0], [0, 0, 20]], [9, 9, 1], "slab-or-2d-candidate"),
            ([[6, 0, 0], [0, 6, 0], [0, 0, 2.46]], [1, 1, 8], "wire-or-1d-candidate"),
            ([[12, 0, 0], [0, 12, 0], [0, 0, 12]], [1, 1, 1], "molecule-or-isolated-candidate"),
        ]
        for vectors, grid, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                config = self.make_case(Path(tmp), vectors, grid)
                self.assertEqual(config["_metadata"]["classification"]["structure_class"], expected)
                self.assertEqual(config["parameters"]["kpoints"], grid)

    def test_user_incar_is_preferred(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.make_case(
                Path(tmp),
                [[4, 0, 0], [0, 4, 0], [0, 0, 4]],
                [6, 6, 6],
                incar="ENCUT=450\nISPIN=2\nISMEAR=-1\nSIGMA=0.05\nGGA=PE\n",
            )
            self.assertEqual(config["parameters"]["encut"], 450)
            self.assertEqual(config["parameters"]["dft"]["ispin"], 2)
            self.assertEqual(config["parameters"]["dft"]["ismear"], -1)
            self.assertEqual(config["parameters"]["dft"]["sigma"], 0.05)

    def test_classification_and_recommendation_thresholds_are_configurable(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.make_case(
                Path(tmp),
                [[6, 0, 0], [0, 6, 0], [0, 0, 2.46]],
                [1, 1, 8],
                config_overrides={
                    "classification": {"vacuum_axis_min_angstrom": 7.0},
                    "parameters": {
                        "heuristics": {
                            "encut_rounding_eV": 30.0,
                            "nbands_minimum": 40,
                        }
                    },
                },
            )
            self.assertEqual(config["_metadata"]["classification"]["structure_class"], "bulk-3d-candidate")
            self.assertEqual(config["parameters"]["encut"], 420.0)
            self.assertEqual(config["parameters"]["nbands"], 40)

    def classify(self, xml_text, structure="bulk-3d-candidate"):
        with tempfile.TemporaryDirectory() as tmp:
            xml_path = Path(tmp) / "vasprun.xml"
            xml_path.write_text(xml_text, encoding="utf-8")
            config = {
                "classification": {
                    "gap_threshold_eV": 0.05,
                    "insulator_gap_threshold_eV": 3.0,
                    "occupation_tolerance": 1e-3,
                },
                "_metadata": {"classification": {"structure_class": structure}},
            }
            return classify_electronic.classify_ground_state(config, xml_path)

    def test_electronic_classes(self):
        semiconductor = self.classify(eigen_xml([[(-1, 2), (1, 0)], [(-0.8, 2), (1.2, 0)]]))
        insulator = self.classify(eigen_xml([[(-2, 2), (2, 0)], [(-1.8, 2), (2.2, 0)]]))
        metal = self.classify(eigen_xml([[(-1, 2), (-0.2, 1), (1, 0)], [(-0.8, 2), (0.2, 1), (1.2, 0)]]))
        self.assertEqual(semiconductor["electronic_class"], "semiconductor")
        self.assertEqual(insulator["electronic_class"], "insulator")
        self.assertEqual(metal["electronic_class"], "metal-or-semimetal")


if __name__ == "__main__":
    unittest.main()
