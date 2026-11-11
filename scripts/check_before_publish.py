#!/usr/bin/env python3
"""Refuse to publish protected files; checks Git tracked/staged paths.

Works before or after git init. A developer can bypass any local script, so
also inspect git status and GitHub upload list yourself.
"""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN_PREFIX=('data/','local_only/','inputs/','processed/','results/','outputs/','data/downloads/','data/raw/','data/processed/')
FORBIDDEN_EXT={'.pdf','.zip','.csv','.xlsx','.xls','.parquet','.sqlite','.db','.pkl','.pickle','.jsonl','.feather'}

def forbidden(rel):
    rel=str(rel).replace('\\','/').lstrip('./')
    return any(rel.startswith(p) for p in FORBIDDEN_PREFIX) or Path(rel).suffix.lower() in FORBIDDEN_EXT

def ls_files(staged=False):
    cmd=['git','ls-files','-z']
    if staged:cmd=['git','diff','--cached','--name-only','-z','--diff-filter=ACMR']
    try:
        out=subprocess.check_output(cmd,cwd=ROOT,stderr=subprocess.DEVNULL)
        return [x.decode('utf8') for x in out.split(b'\0') if x]
    except (FileNotFoundError,subprocess.CalledProcessError):
        return None

def main():
    a=argparse.ArgumentParser();a.add_argument('--staged',action='store_true');args=a.parse_args()
    files=ls_files(args.staged)
    if files is None:
        if args.staged:
            print('ERROR: not a git repository, cannot inspect staged changes.',file=sys.stderr);sys.exit(2)
        print('No git repository initialized yet; .gitignore protects AFTER git init.')
        print('Check manually before publishing; run again with --staged after git add .')
        return
    bad=[f for f in files if forbidden(f)]
    if bad:
        print('BLOCKED: protected files tracked/staged:')
        for f in bad:print('  ',f)
        sys.exit(1)
    print(f'PASS: inspected {len(files)} git {"staged" if args.staged else "tracked"} paths; no PDFs/datasets/archives.')

if __name__=='__main__':main()
