#!/usr/bin/env python3
"""Audit sample coverage, missingness and popularity before running inference.

This script reads user-downloaded local CSVs. It never treats missing data as zero
and never reports selected API requests as completed events.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

def summarize(root: Path) -> dict:
    processed = root/'data/processed'
    out = root/'outputs/audits';out.mkdir(parents=True,exist_ok=True)
    result={}
    paths={
      'review_census':processed/'modern_review_census.csv',
      'review_sample':processed/'review_sample.csv',
      'identity_resolution':processed/'review_enriched.csv',
      'complete_wikipedia':processed/'attention_complete_sample.csv',
      'prior_wikipedia':processed/'popularity/prior_wikipedia_popularity.csv',
      'spotify_charts':processed/'popularity/spotify_modern_event_chart_metrics.csv',
      'youtube_charts':processed/'popularity/youtube_modern_event_chart_metrics.csv'
    }
    frames={}
    for name,path in paths.items():
      if path.exists():
        frames[name]=pd.read_csv(path,low_memory=False)
        result[name]={'n_rows':len(frames[name]),'n_review_ids':int(frames[name].reviewid.nunique()) if 'reviewid' in frames[name] else None}
      else:
        result[name]={'status':'not_present','path':str(path.relative_to(root))}
    if 'review_census' in frames:
      d=frames['review_census'].copy()
      if {'year','score_stratum'}.issubset(d):
        counts=d[d.year.between(2020,2026)].groupby(['year','score_stratum'],dropna=False).size().rename('n').reset_index()
        counts.to_csv(out/'modern_review_counts_by_year_score.csv',index=False)
        result['modern_review_counts_by_year_score']=counts.to_dict('records')
    if 'review_sample' in frames:
      s=frames['review_sample'];result['sample_unique_artist_names']=int(s.artist.nunique()) if 'artist' in s else None
    if 'identity_resolution' in frames:
      d=frames['identity_resolution']; result['identity_coverage']={
        c: int(d[c].notna().sum()) for c in ('artist_mbid','wiki_wikipedia_title','musicbrainz_release_to_review_days') if c in d
      }
    if 'complete_wikipedia' in frames:
      c=frames['complete_wikipedia']; result['complete_event_year_counts']=c.assign(year=pd.to_datetime(c.pub_date,errors='coerce').dt.year).groupby('year').size().to_dict() if 'pub_date' in c else {}
    if 'prior_wikipedia' in frames:
      d=frames['prior_wikipedia'];result['preperiod_popularity']={
        'available':int(pd.to_numeric(d.get('prior_wiki_log_mean'),errors='coerce').notna().sum()) if 'prior_wiki_log_mean' in d else 0,
        'coverage_90pct':int((pd.to_numeric(d.get('prior_wiki_coverage'),errors='coerce')>=.9).sum()) if 'prior_wiki_coverage' in d else 0
      }
    for plat in ('spotify','youtube'):
      key=f'{plat}_charts'
      if key in frames:
        d=frames[key];result[f'{plat}_availability']={
          c:int(d[c].fillna(False).astype(bool).sum()) for c in ('chart_valid_window','prior_chart_lookback_valid') if c in d
        }
    (out/'modern_coverage_summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str),encoding='utf8')
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('.'));args=ap.parse_args()
    print(json.dumps(summarize(args.root.resolve()),indent=2,ensure_ascii=False,default=str))
