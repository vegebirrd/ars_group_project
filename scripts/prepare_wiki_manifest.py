#!/usr/bin/env python3
"""Prepare API requests from already verified Wikipedia titles.

Does not resolve artist/page identities. Fails if titles/dates are missing.
"""
import argparse
from pathlib import Path
import pandas as pd

def prepare(source:pd.DataFrame) -> pd.DataFrame:
    required={'reviewid','pub_date','wiki_wikipedia_title'}
    if not required.issubset(source.columns):
        raise ValueError(f'Missing required fields: {required-set(source.columns)}')
    x=source[['reviewid','pub_date','wiki_wikipedia_title']].copy()
    x=x.rename(columns={'wiki_wikipedia_title':'wiki_title'})
    x=x.dropna(subset=['reviewid','pub_date','wiki_title'])
    x['pub_date']=pd.to_datetime(x.pub_date,errors='coerce')
    x=x.dropna(subset=['pub_date'])
    x['wiki_title']=x.wiki_title.astype(str).str.strip()
    x=x[x.wiki_title.ne('')]
    x['start']=(x.pub_date-pd.Timedelta(days=56)).dt.strftime('%Y%m%d00')
    x['end']=(x.pub_date+pd.Timedelta(days=56)).dt.strftime('%Y%m%d00')
    x['pub_date']=x.pub_date.dt.strftime('%Y-%m-%d')
    return x.drop_duplicates('reviewid')

def main():
    p=argparse.ArgumentParser();p.add_argument('--events',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();d=prepare(pd.read_csv(a.events,low_memory=False))
    a.output.parent.mkdir(parents=True,exist_ok=True);d.to_csv(a.output,index=False)
    print(f'Wrote {len(d)} requests to {a.output}; page identities are UNVERIFIED by this script.')
if __name__=='__main__':main()
