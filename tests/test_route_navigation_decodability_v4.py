from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/diagnose_route_navigation_decodability_v4.py"
OUTPUT_DIR = ROOT / "output/r8_1_route_navigation_decodability_v4"


def load_module():
    spec = importlib.util.spec_from_file_location("diagnose_route_v4", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RouteNavigationDecodabilityV4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.evidence = json.loads(
            (OUTPUT_DIR / "route_navigation_decodability_evidence.json").read_text(encoding="utf-8")
        )
        self.manifest = json.loads((OUTPUT_DIR / "manifest.json").read_text(encoding="utf-8"))

    def test_manifest_hashes_match(self) -> None:
        expected = {
            "capstone_diagnostics.json",
            "eh_frame_fde_excerpt.txt",
            "elf_pt_load_mapping.json",
            "provenance.txt",
            "route_method_metadata_excerpt.txt",
            "route_method_raw_bytes.hex",
            "route_navigation_decodability_evidence.json",
        }
        self.assertEqual({item["path"] for item in self.manifest["files"]}, expected)
        for item in self.manifest["files"]:
            path = OUTPUT_DIR / item["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])

    def test_entry_decode_failure_is_not_whole_range_invalid(self) -> None:
        diagnostics = self.evidence["diagnostics"]
        for name in ("Route..ctor", "Route.ReconstructRoute", "Route.ReconstructNextMap"):
            default = diagnostics[name]["default"]
            self.assertEqual(default["classification"], "ENTRY_DECODE_FAILED")
            self.assertEqual(default["instruction_count"], 0)
            self.assertEqual(default["consumed_bytes"], 0)
            aligned = diagnostics[name]["aligned_resync"]
            self.assertEqual(aligned["classification"], "CANDIDATE_CLUES_ONLY")
            self.assertGreater(aligned["aligned_word_count"], 0)

    def test_synthetic_invalid_entry_keeps_later_aligned_candidates_as_clues(self) -> None:
        try:
            import capstone  # noqa: F401
        except ImportError:
            self.skipTest("capstone optional dependency is unavailable")
        data = b"\xff\xff\xff\xff" + b"\x1f\x20\x03\xd5" + b"\xc0\x03\x5f\xd6"
        default = self.module.default_decode(data, 0x1000)
        self.assertEqual(default["classification"], "ENTRY_DECODE_FAILED")
        self.assertEqual(default["consumed_bytes"], 0)
        aligned = self.module.aligned_decode(data, 0x1000)
        self.assertEqual(aligned["classification"], "CANDIDATE_CLUES_ONLY")
        self.assertEqual(aligned["aligned_valid_count"], 2)

    def test_invalid_binary_fails_before_creating_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            bad_binary = temp_path / "bad.so"
            bad_binary.write_bytes(b"not an elf")
            output = temp_path / "out"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(bad_binary), "--output-dir", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("native library hash does not match", result.stderr)
            self.assertFalse(output.exists())

    def test_route_boundary_and_unknown_call_edge_are_preserved(self) -> None:
        eh_frame = (OUTPUT_DIR / "eh_frame_fde_excerpt.txt").read_text(encoding="utf-8")
        self.assertIn("pc=000000000276d2e4..000000000276d4b8", eh_frame)
        self.assertIn("pc=000000000276d548..000000000276d6ec", eh_frame)
        self.assertIn("pc=000000000276d6ec..000000000276d898", eh_frame)
        self.assertEqual(self.evidence["conclusions"]["route_to_spfa"], "UNKNOWN_MISSING_STATIC_EDGE")
        self.assertIn("candidate clues only", self.evidence["conclusions"]["aligned_decoder"])


if __name__ == "__main__":
    unittest.main()
