"""Losslessly archive this recovery's new large originals only; no production actions."""
from pathlib import Path
import subprocess,gzip,hashlib,json
from prepare import ROOT,BASE,read,write,sha

def main():
 out=BASE/'recovery_attempt_02';journal=out/'gzip_archive_v2.json'
 if journal.exists():raise RuntimeError('Archive already complete; do not repeat broad verification')
 records=[]
 for path in sorted(BASE.rglob('*')):
  if not path.is_file() or path.suffix not in ['.json','.jsonl'] or path.stat().st_size<512*1024:continue
  if path.name not in ['diagnostic_events.json','diagnostic_summary.json','codex_exec.jsonl']:continue
  tracked=subprocess.run(['git','ls-files','--error-unmatch','--',str(path.relative_to(ROOT))],cwd=ROOT,capture_output=True).returncode==0
  if tracked:raise RuntimeError('Refuse to alter historical tracked original: '+str(path))
  raw=path.read_bytes();compressed=gzip.compress(raw,compresslevel=6,mtime=0);restored=gzip.decompress(compressed);assert raw==restored
  target=path.with_name(path.name+'.gz')
  if target.exists():raise RuntimeError('Already archived path')
  target.write_bytes(compressed);assert hashlib.sha256(gzip.decompress(target.read_bytes())).hexdigest()==hashlib.sha256(raw).hexdigest()
  records.append({'original_path':str(path.relative_to(BASE)),'gzip_path':str(target.relative_to(BASE)),'uncompressed_sha256':hashlib.sha256(raw).hexdigest(),'gzip_sha256':sha(target),'uncompressed_bytes':len(raw),'gzip_bytes':len(compressed),'restoration_verified':True})
  write(journal,records);path.unlink()
 # Add storage links without changing the original event identifiers/hashes.
 index=read(out/'key_event_index_v2.json')
 for source,entry in index.items():
  p=ROOT/entry['event_log']
  if not p.exists() and p.with_name(p.name+'.gz').exists():entry['archived_path']=str(p.with_name(p.name+'.gz').relative_to(ROOT))
 write(out/'key_event_index_v2.json',index)
 manifest={}
 for path in sorted(BASE.rglob('*')):
  if not path.is_file() or '__pycache__' in path.parts or path.name.endswith('.lock') or path.name=='artifact_manifest_v2.json':continue
  data=path.read_bytes();item={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
  if path.suffix=='.gz':
   record=next((r for r in records if r['gzip_path']==str(path.relative_to(BASE))),None)
   if record:item.update(uncompressed_sha256=record['uncompressed_sha256'],uncompressed_bytes=record['uncompressed_bytes'],restoration_verified=True)
  manifest[str(path.relative_to(BASE))]=item
 write(out/'artifact_manifest_v2.json',{'schema_version':'R117_RECOVERY_ARCHIVE_MANIFEST_V2','files':manifest,'gzip_files':len(records),'locks_caches_preserved_excluded':True,'historical_manifest_preserved':'../artifact_manifest_v1.json','old_parent_full_events_referenced_not_recopied':True})
 print({'manifest_files':len(manifest),'new_gzip_originals':len(records),'restoration_verified':True})
if __name__=='__main__':main()
