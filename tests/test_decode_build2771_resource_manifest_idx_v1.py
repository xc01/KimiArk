import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/decode_build2771_resource_manifest_idx_v1.py")
SPEC = importlib.util.spec_from_file_location("decode_build2771_resource_manifest_idx_v1", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
Build2771ResourceManifestDecoder = MODULE.Build2771ResourceManifestDecoder
ManifestDecodeError = MODULE.ManifestDecodeError


FIXTURE = Path("tests/fixtures/build2771_small_resource_manifest_idx_v1.idx")


def test_small_idx_framing_and_counts_are_decoded() -> None:
    data = FIXTURE.read_bytes()
    decoder = Build2771ResourceManifestDecoder(data)

    assert len(decoder.signature) == 128
    assert hashlib.sha256(data).hexdigest() == (
        "67c47a74e01cf6418b08dbc4cf1443bb5c0cba8fa3b3f35b6bdc41580559f43c"
    )

    manifest = decoder.decode()
    assert manifest["rawCount"] == 0
    assert len(manifest["bundles"]) == 35
    assert len(manifest["assetToBundleList"]) == 365
    assert manifest["bundles"][0]["name"] == "shaders/other.ab"
    assert manifest["bundles"][0]["allDependencies"] == []
    assert manifest["assetToBundleList"][0]["assetName"] == "config/config"
    assert manifest["assetToBundleList"][0]["path"] == "dyn/config/config.json"


def test_optional_field_beyond_last_vtable_slot_is_absent() -> None:
    decoder = Build2771ResourceManifestDecoder(FIXTURE.read_bytes())
    manifest = decoder.decode()

    assert decoder._slot_offset(decoder.root, 10) == 0
    assert decoder._int(decoder.root, 10) == 0
    assert all(bundle["sccIndex"] != 0 or "sccIndex" in bundle for bundle in manifest["bundles"])


def test_decoder_rejects_truncated_input_before_flatbuffer_access() -> None:
    with pytest.raises(ManifestDecodeError, match="shorter than signature"):
        Build2771ResourceManifestDecoder(b"\0" * 64)


def test_cli_supports_summary_and_query(tmp_path: Path) -> None:
    output = tmp_path / "manifest.json"
    summary = tmp_path / "summary.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/decode_build2771_resource_manifest_idx_v1.py",
            str(FIXTURE),
            "--output",
            str(output),
            "--summary",
            str(summary),
            "--query",
            "config/config",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    decoded = json.loads(result.stdout)
    assert decoded["bundle_count"] == 35
    assert decoded["asset_to_bundle_count"] == 365
    assert decoded["query_matches"][0]["assetName"] == "config/config"
    recorded = json.loads(summary.read_text())
    assert recorded["source_sha256"] == decoded["source_sha256"]
    assert recorded["signature_verification"] == "NOT_PERFORMED"
    assert output.read_text(encoding="utf-8").startswith("{")
