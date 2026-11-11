#!/usr/bin/env python3
"""Download the publicly posted modern Pitchfork catalogue with a content hash.

Source: olievans123/The-Fork, albums.json, latest main branch (1999-2026).
The source is an independent archival project. Historical snapshots are mutable:
keep the downloaded SHA256 and retrieval date for reproducibility.
"""
from __future__ import annotations
import argparse,datetime,hashlib,json
from pathlib import Path
import requests
URL='https://raw.githubusercontent.com/olievans123/The-Fork/main/albums.json'

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('data/downloads/pitchfork-modern/albums.json'));p.add_argument('--force',action='store_true');a=p.parse_args()
 a.out.parent.mkdir(parents=True,exist_ok=True)
 if a.out.exists() and not a.force:print('Already downloaded:',a.out)
 else:
  temp=a.out.with_suffix('.partial')
  headers={'User-Agent':'ars-group-project/1.0 (educational research; source attribution in README)'}
  with requests.get(URL,headers=headers,stream=True,timeout=90) as r:
   r.raise_for_status()
   with temp.open('wb') as f:
    for c in r.iter_content(chunk_size=1024*1024):
     if c:f.write(c)
  temp.replace(a.out)
 sha=hashlib.sha256(a.out.read_bytes()).hexdigest()
 manifest={'source_url':URL,'sha256':sha,'bytes':a.out.stat().st_size,'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'note':'Third-party archive; verify date fields before quantitative claims'}
 a.out.with_suffix('.manifest.json').write_text(json.dumps(manifest,indent=2))
 print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
