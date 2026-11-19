"""Read-only final artifact verification; no production calls."""
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
    proof=read(BASE/'model_provenance_verification.json');assert proof['status']=='PASS' and len(proof['candidates'])==47
    reservation=[read(p) for folder in [BASE/'session/candidates',BASE/'reverification'] for p in folder.glob('*/simulation.simulation_reservation.json')]
    assert len(reservation)==49 and sorted(x['reservation_index'] for x in reservation)==list(range(1,50))
    assert sum(x['status']=='COMPLETED' for x in reservation)==48
    assert sum(x['status']=='FAILED' and x.get('failure_outcome')=='FAILED_BEFORE_START' for x in reservation)==1
    state=read(BASE/'batch_state.json');assert state['stopped'] and state['status']=='COMPLETED_FIVE_ROUNDS_NO_FIXED_FIVE_WIN'
    assert len(state['independent_runs'])==2 and all(all(x['hash_equal'].values()) for x in state['independent_runs'])
    assert read(BASE/'best_selection_v1.json')['candidate_id']=='candidate-040'
    write(BASE/'archive_verification_v1.json',{'status':'PASS','manifest_files':len(actual),'gzip_originals':len(archive),'old_ledgers_unchanged':True,'frozen_start_inputs_unchanged':True,'model_reconstructed_PASS_candidates':47,'counted_reservations':49,'actual_completed_battles':48,'failed_before_battle_counted':1,'independent_reruns':2,'fixed_roster_K':5,'audit_new_battles_models':0})
    print({'archive':'PASS','files':len(actual),'gzip':len(archive),'complete_battles':48,'counted_failed_reservation':1,'new_battles':0})
if __name__=='__main__':main()
