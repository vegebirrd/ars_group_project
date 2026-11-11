#!/usr/bin/env python3
"""Download optional full-review text corpus for LOCAL research processing.

The Hugging Face dataset is third-party sourced; check its dataset card and
publisher's content-use terms before using/re-sharing. Never commit review bodies.
"""
import argparse, hashlib
from pathlib import Path
import requests
URL='https://huggingface.co/datasets/mattismegevand/pitchfork/resolve/main/reviews.csv'

def download(url, target, overwrite=False):
    target=Path(target)
    if target.exists() and not overwrite:
        print('Already downloaded:',target);return target
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(target.suffix+'.part')
    h=hashlib.sha256();size=0
    with requests.get(url,stream=True,timeout=60) as resp:
        resp.raise_for_status()
        with tmp.open('wb') as f:
            for chunk in resp.iter_content(chunk_size=1024*512):
                if chunk:
                    f.write(chunk);h.update(chunk);size+=len(chunk)
    if size < 1024:raise ValueError(f'Unexpectedly small file: {size} bytes; retained {tmp}')
    tmp.replace(target)
    digest=target.with_suffix(target.suffix+'.sha256')
    digest.write_text(f'{h.hexdigest()}  {target.name}\n')
    print('Downloaded:',target,'bytes:',size,'sha256:',h.hexdigest())
    return target

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',default=URL)
    p.add_argument('--output',default='data/downloads/review_text/reviews.csv')
    p.add_argument('--overwrite',action='store_true')
    a=p.parse_args();download(a.url,a.output,a.overwrite)
if __name__=='__main__':main()
