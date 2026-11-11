#!/usr/bin/env python3
"""Prepare 2020-2025 review-frame, audit and historical pre-review exposure."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.extended_sampling import run

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path('data/downloads/pitchfork-modern/albums.json'))
 p.add_argument('--out',type=Path,default=Path('data/processed'));p.add_argument('--start-year',type=int,default=2020)
 p.add_argument('--end-year',type=int,default=2025);p.add_argument('--per-cell',type=int,default=35)
 p.add_argument('--seed',default='ARS2026');a=p.parse_args()
 print(json.dumps(run(a.source,a.out,a.start_year,a.end_year,a.per_cell,a.seed),indent=2))
if __name__=='__main__':main()
