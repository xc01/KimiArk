"""Lossless archival only; no model, tool check, or simulator execution."""
from __future__ import annotations
import gzip
import hashlib
from pathlib import Path
from search_batch import BASE, write


def sha(data):return hashlib.sha256(data).hexdigest()
def eligible(path):return path.is_file() and '__pycache__' not in path.parts and not path.name.endswith('.lock')

def main():
    journal=BASE/'gzip_archive_v1.json'
    import json
    records=json.loads(journal.read_text()) if journal.exists() else []
    archived={r['original_path'] for r in records}
    # Original battle files are preserved as exact, independently decodable gzip bytes; old archives outside BASE are never touched.
    for path in sorted(BASE.rglob('*.json')):
        if path.name not in ['diagnostic_events.json','diagnostic_summary.json']:continue
        if path.stat().st_size<512*1024:continue
        relative=str(path.relative_to(BASE))
        raw=path.read_bytes();compressed=gzip.compress(raw,compresslevel=6,mtime=0)
        if gzip.decompress(compressed)!=raw:raise RuntimeError('Lossless gzip failure')
        target=path.with_name(path.name+'.gz')
        if target.exists() and gzip.decompress(target.read_bytes())!=raw:raise RuntimeError('Conflicting gzip exists')
        target.write_bytes(compressed)
        restored=gzip.decompress(target.read_bytes())
        assert sha(restored)==sha(raw)
        record={'original_path':relative,'gzip_path':str(target.relative_to(BASE)),'uncompressed_sha256':sha(raw),'gzip_sha256':sha(compressed),'uncompressed_bytes':len(raw),'gzip_bytes':len(compressed),'restoration_verified':True}
        if relative not in archived:records.append(record);archived.add(relative)
        write(journal,records)
        path.unlink()
    files={}
    for path in sorted(BASE.rglob('*')):
        if not eligible(path) or path.name=='artifact_manifest_v1.json':continue
        data=path.read_bytes();item={'sha256':sha(data),'bytes':len(data)}
        if path.suffix=='.gz':
            restored=gzip.decompress(data)
            item.update({'uncompressed_sha256':sha(restored),'uncompressed_bytes':len(restored),'restoration_verified':True})
            assert not restored.startswith(bytes([31,139])), 'Double gzip detected'
        files[str(path.relative_to(BASE))]=item
    write(BASE/'artifact_manifest_v1.json',{'schema_version':'R115_ARCHIVE_MANIFEST_V1','scope':'Only this batch; no repeated unrelated manifests/tests','files':files,'gzip_files':len(records),'locks_and_python_caches_preserved_but_not_committed':True,'old_parent_artifacts':'Referenced by original hashes, not rewritten'})
    print({'files':len(files),'gzipped_originals':len(records),'restoration_verified':True})

if __name__=='__main__':main()
