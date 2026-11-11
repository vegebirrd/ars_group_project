#!/usr/bin/env python3
"""P4KxSpotify -> typed review inventory and a preregistered score-stratified API sample.

Sample frame: reviews with a single nonempty artist string, a parsable review date,
and year in the chosen range. All low-score events are retained up to `per_stratum`,
with deterministic hashing used for the middle/high strata. One artist-album-date
combination is treated as one event; an audit of duplicate records is retained.
"""
from __future__ import annotations
import argparse, hashlib, json, unicodedata
from pathlib import Path
import pandas as pd

def normalize(s):
    return ' '.join(unicodedata.normalize('NFKC',str(s)).casefold().split())

def build(source: pd.DataFrame, year_min=2018,year_max=2019,per_stratum=66,seed='20261022'):
    needed={'artist','album','reviewdate','score'}
    if needed-set(source.columns):raise ValueError(f'Missing columns: {sorted(needed-set(source.columns))}')
    x=source.copy().reset_index(drop=True)
    x['source_row']=x.index+1
    x['reviewid']=x.source_row.map(lambda v:f'p4k_{v:08d}')
    x['artist']=x.artist.astype('string').str.strip()
    x['title']=x.album.astype('string').str.strip()
    x['score']=pd.to_numeric(x.score,errors='coerce')
    x['pub_date']=pd.to_datetime(x.reviewdate,errors='coerce').dt.normalize()
    x['year']=x.pub_date.dt.year
    x=x[x.year.between(year_min,year_max)&x.score.between(0,10)&x.artist.notna()&x.title.notna()&(x.artist!='')&(x.title!='')].copy()
    x['artist_norm']=x.artist.map(normalize)
    x['title_norm']=x.title.map(normalize)
    x['genres_json']=x.get('genre',pd.Series(index=x.index,dtype='str')).map(lambda v:json.dumps([str(v)] if pd.notna(v) and str(v).strip() else []))
    x['pub_date']=x.pub_date.dt.strftime('%Y-%m-%d')
    x['dedupe_key']=x.artist_norm+'||'+x.title_norm+'||'+x.pub_date
    duplicates=x[x.duplicated('dedupe_key',keep='first')].copy()
    x=x.drop_duplicates('dedupe_key').copy()
    x['score_stratum']=pd.cut(x.score,[-.00001,5,8,10.000001],right=False,labels=['low','middle','high']).astype(str)
    # A reproducible, independent rank inside each stratum; not outcome-selected.
    x['selection_hash']=x.reviewid.map(lambda rid:hashlib.sha256(f'{seed}|{rid}'.encode()).hexdigest())
    sample=x.sort_values('selection_hash').groupby('score_stratum',group_keys=False).head(per_stratum).sort_values('pub_date').copy()
    fractions=(sample.score_stratum.value_counts()/x.score_stratum.value_counts()).to_dict()
    sample['selection_probability']=sample.score_stratum.map(fractions).astype(float)
    return x,sample,duplicates

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path('data/downloads/pitchfork/output-data.csv'))
    p.add_argument('--out',type=Path,default=Path('data/processed'))
    p.add_argument('--start-year',type=int,default=2018);p.add_argument('--end-year',type=int,default=2019)
    p.add_argument('--per-stratum',type=int,default=66);p.add_argument('--seed',default='20261022')
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    raw=pd.read_csv(args.source,low_memory=False)
    eligible,sample,duplicates=build(raw,args.start_year,args.end_year,args.per_stratum,args.seed)
    eligible.to_csv(args.out/'eligible_reviews.csv',index=False)
    sample.to_csv(args.out/'review_sample.csv',index=False)
    duplicates.to_csv(args.out/'duplicate_review_rows.csv',index=False)
    summary={'raw_rows':len(raw),'eligible_events':len(eligible),'selected_events':len(sample),'duplicates_removed':len(duplicates),
             'eligible_by_score':eligible.score_stratum.value_counts().to_dict(),'sampled_by_score':sample.score_stratum.value_counts().to_dict(),
             'years':[args.start_year,args.end_year],'seed':args.seed}
    (args.out/'sample_manifest.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
