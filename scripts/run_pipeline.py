#!/usr/bin/env python3
"""Collect and prepare research datasets. R estimation runs separately.

Modern 2020–2025: python scripts/run_pipeline.py --cohort modern --stage all --email researcher@example.edu
Historical:       python scripts/run_pipeline.py --cohort historical --stage all --email researcher@example.edu
R model:          Rscript run_r.R --stage all
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def execute(script: str, *flags: str) -> None:
    command = [sys.executable, str(ROOT / 'scripts' / script), *map(str, flags)]
    print('>', ' '.join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)

def run_stage(stage: str, cohort: str, args: argparse.Namespace) -> None:
    modern = cohort == 'modern'
    if stage == 'download':
        if modern:
            execute('download_extended_reviews.py')
        else:
            execute('download_public_data.py', 'all')
    elif stage == 'prepare':
        if modern:
            execute('prepare_extended_reviews.py', '--start-year', str(args.start_year),
                    '--end-year', str(args.end_year), '--per-cell', str(args.per_cell))
        else:
            execute('prepare_reviews.py', '--start-year', str(args.start_year),
                    '--end-year', str(args.end_year))
    elif stage == 'match':
        flags = ['--email', args.email, '--max-events', str(args.max_events)]
        if args.overrides:
            flags += ['--overrides', args.overrides]
        execute('resolve_musicbrainz.py', *flags)
    elif stage == 'wikipedia':
        execute('prepare_wiki_manifest.py', '--events', 'data/processed/review_enriched.csv',
                '--output', 'data/processed/wiki_manifest.csv')
        execute('fetch_wikimedia_pageviews.py', '--manifest', 'data/processed/wiki_manifest.csv',
                '--output', 'data/raw/wikipedia')
        execute('build_event_panel.py')
    elif stage == 'popularity':
        execute('collect_prior_popularity.py', '--email', args.email)
    elif stage == 'charts':
        if modern:
            execute('download_modern_charts.py', '--platform', 'both',
                    '--start-year', str(args.charts_start), '--end-year', str(args.end_year))
            execute('analyze_modern_charts.py')
        else:
            # The legacy Spotify weekly chart is downloaded with stage=download.
            execute('build_prior_chart_popularity.py')
            command = [sys.executable, '-m', 'src.spotify_from_downloads',
                       '--reviews', 'data/processed/eligible_reviews.csv',
                       '--charts', 'data/downloads/spotify/spotify-top-200-dataset.csv',
                       '--out', 'outputs']
            print('>', ' '.join(command), flush=True)
            subprocess.run(command, cwd=ROOT, check=True)
    elif stage == 'audit':
        execute('audit_modern_sample.py')
    else:
        raise ValueError('Unknown stage ' + stage)

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=['modern','historical'], default='modern')
    parser.add_argument('--stage', choices=['all','download','prepare','match','wikipedia',
                    'popularity','charts','audit'], default='all')
    parser.add_argument('--email', help='Research contact email for MusicBrainz/Wikimedia')
    parser.add_argument('--start-year', type=int)
    parser.add_argument('--end-year', type=int)
    parser.add_argument('--charts-start', type=int, default=2018)
    parser.add_argument('--per-cell', type=int, default=35)
    parser.add_argument('--max-events', type=int, default=0)
    parser.add_argument('--overrides', type=str)
    args=parser.parse_args()
    if args.start_year is None: args.start_year = 2020 if args.cohort=='modern' else 2018
    if args.end_year is None: args.end_year = 2025 if args.cohort=='modern' else 2019
    if args.start_year > args.end_year: parser.error('start-year must not exceed end-year')
    steps=(['download','prepare','match','wikipedia','popularity','charts','audit']
           if args.cohort=='modern' else ['download','prepare','match','wikipedia','charts'])
    selected=steps if args.stage=='all' else [args.stage]
    if any(s in ('match','popularity') for s in selected) and not args.email:
        parser.error('--email researcher@example.edu is needed for artist identification')
    if args.cohort=='historical' and any(s in ('popularity','audit') for s in selected):
        parser.error('This stage belongs to the modern cohort')
    for step in selected: run_stage(step, args.cohort, args)
    print('Collection complete. Run: Rscript run_r.R --stage all', flush=True)

if __name__=='__main__':main()
