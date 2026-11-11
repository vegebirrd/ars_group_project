#!/usr/bin/env python3
"""Download per-year Spotify Top 200/YouTube Top 100 from Zenodo 23644526.

Zenodo record contains all global weekly chart weeks for 2018–2026; countries
outside global/Türkiye are sampled less frequently. The tables give listed
streams/views and RANKS, not total market consumption or album unit sales.
"""
import argparse,datetime,hashlib,json
from pathlib import Path
import requests
ROOT='https://zenodo.org/records/23644526/files'
CHECKS={
('spotify',2018):'fc020ff7c818e41be8a90bebff6037f6',('spotify',2019):'162e0f0bc2f6fae71c3a6fb4f2fd10d2',
('youtube',2018):'bf1501fb8fbd01763e92eb39f212ad08',('youtube',2019):'58fdec6bcdbb1d590fd5eee0aa40e4ae',
('spotify',2020):'29ba387ea33529adaac83a52df07a8f6',('spotify',2021):'0691d1f4bce5a929fac86edf7be51b44',
('spotify',2022):'38b620febcbcfc6522b23300cb7dba78',('spotify',2023):'e9241d12658b3f38721419877453b83b',
('spotify',2024):'fe8654d0b443c2008333448546d35109',('spotify',2025):'a42bec090ef5e95584ba3b498bf4fe84',
('youtube',2020):'cfc1097ed0e93435281a5f6180d34458',('youtube',2021):'4da53365358afa2b65a921e9e01f85c5',
('youtube',2022):'ad15509982a728bae07144b1531f5573',('youtube',2023):'7756c5629fa4b64e1c421f56e34837e6',
('youtube',2024):'f6e9e226d783add04cfe313f50991ba6',('youtube',2025):'3734d62c5a74813efa8afedebd9cc91b',
}

def filename(platform,year):
 return f"{'spotify_top200' if platform=='spotify' else 'youtube_top100'}_positions_{year}.csv.gz"

def download(platform,year,out,force=False):
 fname=filename(platform,year);dir=out/platform;dir.mkdir(parents=True,exist_ok=True)
 path=dir/fname
 url=f'{ROOT}/{fname}?download=1';md5=CHECKS.get((platform,year))
 if not path.exists() or force:
  temp=path.with_name(path.name+'.partial')
  with requests.get(url,stream=True,timeout=90,headers={'User-Agent':'ARS-GroupProject/1.0 (educational research)'}) as r:
   r.raise_for_status()
   with temp.open('wb') as f:
    for chunk in r.iter_content(1024*1024):
     if chunk:f.write(chunk)
  content=temp.read_bytes()
  if md5 and hashlib.md5(content).hexdigest()!=md5:
   temp.unlink(missing_ok=True)
   raise ValueError('Checksum mismatch; dataset may have changed: '+fname)
  temp.replace(path)
 data=path.read_bytes()
 if md5 and hashlib.md5(data).hexdigest()!=md5:raise ValueError('Bad cached file: '+fname)
 return dict(source_url=url,path=str(path),md5=hashlib.md5(data).hexdigest(),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))

def main():
 p=argparse.ArgumentParser();p.add_argument('--platform',choices=['spotify','youtube','both'],default='both')
 p.add_argument('--start-year',type=int,default=2018);p.add_argument('--end-year',type=int,default=2025)
 p.add_argument('--out',type=Path,default=Path('data/downloads/charts-modern'));p.add_argument('--force',action='store_true');a=p.parse_args()
 pairs=[(p,y) for p in (['spotify','youtube'] if a.platform=='both' else [a.platform]) for y in range(a.start_year,a.end_year+1)]
 if any(x not in CHECKS for x in pairs):p.error('Verified checksums cover 2018–2025 only')
 result=[]
 for platform,year in pairs:
  print('Fetching',platform,year,flush=True);result.append(download(platform,year,a.out,a.force))
 a.out.mkdir(parents=True,exist_ok=True)
 (a.out/'download_manifest.json').write_text(json.dumps({'record_doi':'10.5281/zenodo.23644526','retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':result},indent=2))
 print(f'Saved {len(result)} annual chart files')
if __name__=='__main__':main()
