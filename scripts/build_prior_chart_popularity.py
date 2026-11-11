#!/usr/bin/env python3
"""Historical Top-200 PRIOR visibility: never use today's artist popularity.

Each event needs a complete observed global chart calendar for the lookback.
Charted streams are lower-bound / Top-200-only exposure, not total plays.
Historical repository through ~2021 will yield NA, not 0, for later years.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd,numpy as np


def norm(x):
    import re, unicodedata
    x=unicodedata.normalize('NFKD',str(x)).casefold()
    return re.sub(r'[^a-z0-9]+',' ',''.join(c for c in x if not unicodedata.combining(c))).strip()


def prior_charts(reviews:pd.DataFrame,charts:pd.DataFrame,lookback_weeks=52,blackout_weeks=8):
    d=charts.copy();d['week']=pd.to_datetime(d.week,errors='coerce');d=d.dropna(subset=['week'])
    d['artist_norm']=d.artist_name.map(norm)
    d['streams']=pd.to_numeric(d['streams'],errors='coerce')
    artists=d[['artist_norm','artist_id']].drop_duplicates()
    names=artists.groupby('artist_norm').artist_id.nunique()
    ids=artists[artists.artist_norm.isin(names[names.eq(1)].index)].drop_duplicates('artist_norm')
    d=d.drop_duplicates(['artist_id','track_id','week'])
    weeks=pd.DatetimeIndex(sorted(d.week.unique()))
    totals=d.groupby(['artist_id','week'],as_index=False).agg(visible_streams=('streams','sum'),charted_tracks=('track_id','nunique'))
    x=reviews.copy();x['artist_norm']=x.artist.map(norm)
    x=x.merge(ids,on='artist_norm',how='left',validate='many_to_one')
    result=[]
    for r in x.itertuples(index=False):
        t=pd.to_datetime(r.pub_date)
        end=t-pd.Timedelta(weeks=blackout_weeks)
        ref=weeks[(weeks<end)].sort_values()[-lookback_weeks:]
        row={'reviewid':r.reviewid,'prior_chart_match':pd.notna(r.artist_id),
             'prior_chart_calendar_weeks':len(ref),'prior_chart_weeks':np.nan,
             'prior_chart_visible_streams':np.nan,'prior_chart_visible_weeks_share':np.nan,
             'prior_chart_observable':False}
        # If chart archive doesn't include all lookback weeks, don't assign zero.
        if len(ref)==lookback_weeks and pd.notna(r.artist_id):
            g=totals[(totals.artist_id==r.artist_id)&totals.week.isin(ref)]
            row.update(prior_chart_weeks=len(g),prior_chart_visible_streams=g.visible_streams.sum(),
                       prior_chart_visible_weeks_share=len(g)/lookback_weeks,
                       prior_chart_observable=True)
        result.append(row)
    return pd.DataFrame(result)


def main():
    p=argparse.ArgumentParser();p.add_argument('--reviews',type=Path,default=Path('data/processed/review_sample.csv'))
    p.add_argument('--charts',type=Path,default=Path('data/downloads/spotify/spotify-top-200-dataset.csv'))
    p.add_argument('--out',type=Path,default=Path('data/processed/popularity/prior_spotify_visibility.csv'))
    a=p.parse_args();a.out.parent.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(a.charts,sep=';',usecols=['artist_name','artist_id','track_id','week','streams'])
    result=prior_charts(pd.read_csv(a.reviews),d)
    result.to_csv(a.out,index=False)
    print(result.prior_chart_observable.value_counts(dropna=False).to_dict())
if __name__=='__main__':main()
