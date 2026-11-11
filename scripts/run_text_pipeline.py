#!/usr/bin/env python3
"""Run optional expert-review text, YouTube audience-comment, or both branches.

Usage:
  python scripts/run_text_pipeline.py --stage expert
  python scripts/run_text_pipeline.py --stage audience
  python scripts/run_text_pipeline.py --stage all

Full-text corpus download is opt-in; YouTube IDs are manually verified.
"""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(command):
    print('>',sys.executable,*command,flush=True)
    subprocess.run([sys.executable,*command],cwd=ROOT,check=True)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=['expert','audience','all'],default='all')
    p.add_argument('--download-review-text',action='store_true')
    p.add_argument('--max-pages',type=int,default=3)
    a=p.parse_args()
    if a.stage in ('expert','all'):
        if a.download_review_text:run(['scripts/download_review_text.py'])
        run(['scripts/prepare_review_text.py'])
    if a.stage in ('audience','all'):
        manifest=Path('data/processed/youtube_video_manifest.csv')
        if not manifest.exists():
            run(['scripts/make_youtube_manifest.py'])
            raise SystemExit('Fill the new manifest video_id and video_match_reason fields before collecting.')
        run(['scripts/fetch_youtube_comments.py','--max-pages',str(a.max_pages)])
    print('Text branch done. Run: Rscript run_r.R --stage text')
if __name__=='__main__':main()
