#!/usr/bin/env python3
"""Link a separately acquired full-text Pitchfork review corpus to our review IDs.

Source suggestion: https://huggingface.co/datasets/mattismegevand/pitchfork
The original Zenodo P4KxSpotify CSV contains metadata and audio features, not
review bodies. Local review text is never copied to a GitHub-tracked path.

Matching is artist+album exact after Unicode normalization, then review date
within the specified tolerance and score agreement. Ambiguous matches fail closed.
"""
from __future__ import annotations
import argparse, re, sys, unicodedata
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.text_research import text_features

ALIASES={"artist":["artist","artists"],"album":["album","title","album_title"],
         "review_date":["release_date","reviewdate","review_date","pub_date","date","publish_datetime"],
         "score":["rating","score"],"text":["review","article","content","review_text"]}

def normalize(v):
    v=unicodedata.normalize('NFKD',str(v or '')).casefold().strip()
    v=''.join(ch for ch in v if not unicodedata.combining(ch))
    return ' '.join(re.findall(r'\w+',v))

def choose_column(df, candidates, required=True):
    name=next((c for c in candidates if c in df.columns),None)
    if required and name is None:raise ValueError(f'Missing any of columns: {candidates}')
    return name

def link_text_reviews(sample:pd.DataFrame, text_source:pd.DataFrame, max_days=3, max_score_gap=0.11):
    """Return matched features and a one-row-per-event audit.

    Prefer exact date and score; no nearest-neighbor guessing across multiple
    candidate reviews of the same artist+album.
    """
    s=sample.copy(); t=text_source.copy()
    if 'reviewid' not in s: raise ValueError('Sample needs reviewid')
    artist=choose_column(t,ALIASES['artist']);album=choose_column(t,ALIASES['album'])
    date=choose_column(t,ALIASES['review_date']);score=choose_column(t,ALIASES['score'],False)
    body=choose_column(t,ALIASES['text'])
    for d in (s,t):
        d['artist_key']=d['artist'].map(normalize) if d is s else d[artist].map(normalize)
        d['album_key']=d['title'].map(normalize) if d is s else d[album].map(normalize)
    s['review_day']=pd.to_datetime(s['pub_date'],errors='coerce').dt.normalize()
    t['text_day']=pd.to_datetime(t[date],errors='coerce').dt.normalize()
    t['text_score']=pd.to_numeric(t[score],errors='coerce') if score else np.nan
    t['text_body']=t[body].fillna('').astype(str)
    t=t[t.text_body.str.strip().str.len()>0].copy()
    t['source_index']=t.index
    candidates=s.merge(t[['artist_key','album_key','text_day','text_score','text_body','source_index']],
                       on=['artist_key','album_key'],how='left')
    candidates['day_difference']=(candidates.text_day-candidates.review_day).dt.days.abs()
    candidates['score_difference']=(pd.to_numeric(candidates.text_score,errors='coerce') -
                                    pd.to_numeric(candidates.score,errors='coerce')).abs()
    good=candidates[(candidates.day_difference<=max_days) &
                    (candidates.score_difference.isna() | (candidates.score_difference<=max_score_gap)) &
                    candidates.source_index.notna()].copy()
    audit=[];result=[]
    for rid,g in s.groupby('reviewid',sort=False):
        c=good[good.reviewid==rid]
        # Repeated identical source lines are not distinct matches.
        unique=c.drop_duplicates('text_body')
        if len(unique)==1:
            r=unique.iloc[0]
            z=text_features(r.text_body)
            result.append(dict(reviewid=rid, text_source='fulltext_corpus',
                               text_match_day_gap=int(r.day_difference), **z))
            status='matched'
        elif len(unique)>1:status='ambiguous'
        else:status='unmatched'
        audit.append(dict(reviewid=rid, artist=g.artist.iloc[0], album=g.title.iloc[0],
                          pub_date=g.pub_date.iloc[0], status=status, candidate_count=len(unique)))
    return pd.DataFrame(result),pd.DataFrame(audit)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus',default='data/downloads/review_text/reviews.csv')
    p.add_argument('--reviews',default='data/processed/review_sample.csv')
    p.add_argument('--output',default='data/processed/review_text_features.csv')
    p.add_argument('--audit',default='data/processed/review_text_match_audit.csv')
    p.add_argument('--max-days',type=int,default=3)
    args=p.parse_args()
    if not Path(args.corpus).exists():p.error('Download optional full-text corpus first; see docs/TEXT_AS_DATA.md')
    corpus=pd.read_csv(args.corpus,low_memory=False)
    sample=pd.read_csv(args.reviews,low_memory=False)
    features,audit=link_text_reviews(sample,corpus,max_days=args.max_days)
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    features.to_csv(args.output,index=False);audit.to_csv(args.audit,index=False)
    print(audit.status.value_counts().to_string());print(f'Written {len(features)} matched numeric text-feature rows')
if __name__=='__main__':main()
