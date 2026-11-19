"""R122 archive-only hash/accounting verification."""
import gzip,hashlib
from prepare import BASE,ROOT,read,write,sha
from archive_batch import EXCLUDED,eligible
def main():
    manifest=read(BASE/'artifact_manifest_v1.json')
    actual={str(p.relative_to(BASE)) for p in BASE.rglob('*') if eligible(p) and p.name not in EXCLUDED}
    assert actual==set(manifest['files'])
    for name,item in manifest['files'].items():
        data=(BASE/name).read_bytes();assert hashlib.sha256(data).hexdigest()==item['sha256'],name
        if name.endswith('.gz'):
            restored=gzip.decompress(data);assert not restored.startswith(b'\x1f\x8b');assert hashlib.sha256(restored).hexdigest()==item['uncompressed_sha256']
    archive=read(BASE/'gzip_archive_v1.json')
    for item in archive:
        assert not (BASE/item['original_path']).exists()
        assert hashlib.sha256(gzip.decompress((BASE/item['gzip_path']).read_bytes())).hexdigest()==item['uncompressed_sha256']
    for name,value in read(BASE/'sealed_ledger_hashes.json').items():assert sha(ROOT/name)==value,name
    for name,value in read(BASE/'session/codex_cli/frozen_start_manifest.json')['inputs'].items():assert sha(ROOT/name)==value,name
    for name,value in read(BASE/'mechanic_patch_identity.json')['files_sha256'].items():assert sha(ROOT/name)==value,name
    proof=read(BASE/'model_provenance_verification.json');assert proof['status']=='PASS' and len(proof['candidates'])==32
    reservations=[read(p) for directory in [BASE/'session/candidates',BASE/'reverification'] for p in directory.glob('*/simulation.simulation_reservation.json')]
    assert len(reservations)==33 and sorted(r['reservation_index'] for r in reservations)==list(range(1,34))
    assert all(r['status']=='COMPLETED' and r['result_saved'] for r in reservations)
    state=read(BASE/'batch_state.json');assert state['stopped'] and len(state['independent_runs'])==1 and all(state['independent_runs'][0]['hash_equal'].values())
    assert read(BASE/'best_selection_v1.json')['candidate_id']=='candidate-023'
    write(BASE/'archive_verification_v1.json',{'status':'PASS','manifest_files':len(actual),'gzip_originals':len(archive),'old_ledger_hashes_unchanged':True,'model_inputs_and_mechanic_code_hashes_unchanged':True,'model_reconstructed_PASS_candidates':32,'actual_complete_simulations':33,'independent_reruns':1,'roster_K':5,'baseline_lineage_caveat_preserved':True,'new_battles_by_audit':0})
    print({'archive':'PASS','files':len(actual),'gzip':len(archive),'complete_battles':33,'new_battles':0})
if __name__=='__main__':main()
