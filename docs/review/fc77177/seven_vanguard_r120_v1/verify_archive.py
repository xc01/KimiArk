"""Read-only evidence/archive verification, derived result only."""
import gzip,hashlib
from experiment import BASE, ROOT, read, write, sha
from archive_batch import EXCLUDED, eligible

def main():
    manifest=read(BASE/"artifact_manifest_v1.json")
    paths={str(p.relative_to(BASE)) for p in BASE.rglob("*") if eligible(p) and p.name not in EXCLUDED}
    assert paths==set(manifest["files"])
    for name,record in manifest["files"].items():
        data=(BASE/name).read_bytes()
        assert hashlib.sha256(data).hexdigest()==record["sha256"],name
        if name.endswith(".gz"):
            raw=gzip.decompress(data)
            assert not raw.startswith(b"\x1f\x8b")
            assert hashlib.sha256(raw).hexdigest()==record["uncompressed_sha256"]
    for r in read(BASE/"gzip_archive_v1.json"):
        assert not (BASE/r["original_path"]).exists()
        assert hashlib.sha256(gzip.decompress((BASE/r["gzip_path"]).read_bytes())).hexdigest()==r["uncompressed_sha256"]
    for name,value in read(BASE/"sealed_ledger_hashes.json").items():assert sha(ROOT/name)==value,name
    counts=read(BASE/"verification_v1.json")
    assert counts["status"]=="PASS" and counts["actual_completed_reservations"]==2
    assert counts["model_calls"]==counts["CLI_starts"]==0
    assert read(BASE/"batch_closed.json")["closed"]
    write(BASE/"archive_verification_v1.json",{"status":"PASS","manifest_files":len(paths),"gzip_originals":len(read(BASE/"gzip_archive_v1.json")),"actual_completed_runs":2,"old_ledgers_unchanged":True,"new_models_checks_battles_by_audit":0})
    print({"archive":"PASS","files":len(paths),"new_battles":0})

if __name__=="__main__":main()
