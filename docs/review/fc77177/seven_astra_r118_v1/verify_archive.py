"""Read-only production evidence audit; writes one derived audit result only."""
import gzip
import hashlib
from prepare import BASE, ROOT, read, write, sha
from archive_batch import eligible, EXCLUDED

def main():
    manifest = read(BASE / "artifact_manifest_v1.json")
    actual = {str(p.relative_to(BASE)) for p in BASE.rglob("*") if eligible(p) and p.name not in EXCLUDED}
    assert actual == set(manifest["files"]), "Manifest coverage changed"
    for name, record in manifest["files"].items():
        p = BASE / name
        raw = p.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record["sha256"], name
        assert len(raw) == record["bytes"], name
        if p.suffix == ".gz":
            restored = gzip.decompress(raw)
            assert not restored.startswith(b"\x1f\x8b")
            assert hashlib.sha256(restored).hexdigest() == record["uncompressed_sha256"], name
    archives = read(BASE / "gzip_archive_v1.json")
    for record in archives:
        assert not (BASE / record["original_path"]).exists(), "Duplicate uncompressed original"
        compressed = (BASE / record["gzip_path"]).read_bytes()
        assert hashlib.sha256(compressed).hexdigest() == record["gzip_sha256"]
        assert hashlib.sha256(gzip.decompress(compressed)).hexdigest() == record["uncompressed_sha256"]
    for name, expected in read(BASE / "sealed_ledger_hashes.json").items():
        assert sha(ROOT / name) == expected, name
    for name, expected in read(BASE / "session/codex_cli/frozen_start_manifest.json")["inputs"].items():
        assert sha(ROOT / name) == expected, name
    provenance = read(BASE / "model_provenance_verification.json")
    assert provenance["status"] == "PASS" and len(provenance["candidates"]) == 18
    reservations = [read(p) for root in [BASE / "session/candidates", BASE / "reverification"] for p in root.glob("*/simulation.simulation_reservation.json")]
    assert len(reservations) == 19
    assert sorted(r["reservation_index"] for r in reservations) == list(range(1, 20))
    assert all(r["status"] == "COMPLETED" and r["result_saved"] for r in reservations)
    state = read(BASE / "batch_state.json")
    assert state["stopped"] and state["status"] == "COMPLETED_FIVE_ASTRA_ROUNDS_NO_WIN"
    independent = state["independent_runs"][0]
    assert independent["budget_before"] == 18 and independent["budget_after"] == 19 and all(independent["hash_equal"].values())
    write(BASE / "archive_verification_v1.json", {"status": "PASS", "manifest_files": len(actual), "lossless_gzip_originals": len(archives), "old_ledger_hashes_unchanged": True, "frozen_start_inputs_unchanged": True, "model_parameter_reconstructed_PASS_candidates": 18, "actual_distinct_completed_reservations": 19, "independent_rerun_exact_hashes": True, "closed_after_five_rounds": True, "new_models_checks_battles_by_audit": 0})
    print({"status": "PASS", "manifest_files": len(actual), "gzip_originals": len(archives), "real_runs_verified": 19, "new_battles": 0})

if __name__ == "__main__":
    main()
