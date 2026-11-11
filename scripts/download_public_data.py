#!/usr/bin/env python3
"""Download *public source files* only — NOT the full entity-linked analysis dataset.

- Zenodo P4KxSpotify original reviews (official published MD5 checksum).
- Third-party Spotify historical global weekly Top-200 CSV.
Source revisions may change. Logs URL, file size, SHA256, timestamp, HTTP metadata.
"""
from __future__ import annotations
import argparse,hashlib,json,datetime
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
FILES={
 'pitchfork':{
   'url':'https://zenodo.org/records/3603330/files/output-data.csv?download=1',
   'path':'pitchfork/output-data.csv',
   'md5':'ef1de60923bc1ee13d946c6a05e54a0d',
   'description':'18,403 Pitchfork reviews in P4KxSpotify (Zenodo DOI:10.5281/zenodo.3603330)'},
 'spotify':{
   'url':'https://raw.githubusercontent.com/younver/spotify-top-200-dataset/main/spotify-top-200-dataset.csv',
   'path':'spotify/spotify-top-200-dataset.csv',
   'md5':None,
   'description':'Third-party global weekly Top 200 snapshot (2017-2021), not all streams'},
}


def digests(filename:Path):
    md5=hashlib.md5();sha=hashlib.sha256();size=0
    with filename.open('rb') as handle:
        for chunk in iter(lambda:handle.read(2**20),b''):
            md5.update(chunk);sha.update(chunk);size+=len(chunk)
    return {'md5':md5.hexdigest(),'sha256':sha.hexdigest(),'bytes':size}


def download(name,out_root,force=False,timeout=75):
    info=FILES[name];dest=out_root/info['path'];dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists() and not force:
        print('Existing file; skip:',dest)
        return {'source':name,'file':str(dest),'skipped':True,**digests(dest)}
    temp=dest.with_suffix('.partial')
    headers={'User-Agent':'ARS-Music-Criticism/1.0 (academic research; source attribution in README)'}
    with requests.get(info['url'],headers=headers,stream=True,timeout=timeout) as resp:
        resp.raise_for_status()
        with temp.open('wb') as fh:
            for chunk in resp.iter_content(chunk_size=2**20):
                if chunk:fh.write(chunk)
        server_type=resp.headers.get('Content-Type','')
    sums=digests(temp)
    if info['md5'] and sums['md5'].lower()!=info['md5']:
        temp.unlink(missing_ok=True)
        raise ValueError(f"MD5 mismatch for {name}: downloaded {sums['md5']}, source declares {info['md5']}")
    temp.replace(dest)
    print('Downloaded:',name,dest,sums['bytes'],'bytes')
    return {'source':name,'url':info['url'],'description':info['description'],'file':str(dest),
            'downloaded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'content_type':server_type,**sums}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('dataset',choices=['all',*FILES])
    p.add_argument('--out',type=Path,default=ROOT/'data/downloads')
    p.add_argument('--force',action='store_true')
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    manifest=a.out/'download_manifest.json'
    existing=json.loads(manifest.read_text(encoding='utf8')) if manifest.exists() else {}
    for name in FILES if a.dataset=='all' else [a.dataset]:
        existing[name]=download(name,a.out,force=a.force)
        manifest.write_text(json.dumps(existing,ensure_ascii=False,indent=2),encoding='utf8')
    print('Done. Note: source downloads DO NOT reproduce wiki event matching or 196-event sample.')

if __name__=='__main__':main()
