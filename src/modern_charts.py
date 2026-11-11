"""Prepare weekly Global Spotify / YouTube chart exposure & prior popularity.

Only global weekly charts: national country weeks are sampled every fourth week.
All charts are censored at platform Top 200/Top 100. Missing calendar week is
NEVER a zero. A charted absence is zero *visible* chart streams/views only.
"""
from __future__ import annotations
import re, unicodedata
from pathlib import Path
import numpy as np,pandas as pd


def norm(x):
 s=unicodedata.normalize('NFKD',str(x or '')).casefold()
 return re.sub(r'[^a-z0-9]+',' ',''.join(c for c in s if not unicodedata.combining(c))).strip()


def read_weekly(directory:Path,platform='spotify'):
 pattern=('spotify_top200' if platform=='spotify' else 'youtube_top100')+'_positions_*.csv.gz'
 files=sorted(directory.glob(pattern));
 if not files:raise FileNotFoundError(f'No {platform} annual chart files in {directory}')
 chunks=[]
 for f in files:
  z=pd.read_csv(f,compression='gzip',low_memory=False)
  cols={'cc','week_end','rank','artists','title'}
  if not cols.issubset(z):raise ValueError(f'Missing columns {cols-set(z.columns)} in {f}')
  z=z[z.cc.astype(str).str.lower().eq('global')].copy()
  z['week_end']=pd.to_datetime(z.week_end,errors='coerce')
  z['rank']=pd.to_numeric(z['rank'],errors='coerce')
  z=z.dropna(subset=['week_end','rank'])
  z['lead_artist']=z.artists.fillna('').astype(str).str.split(r'\s*\|\s*').str[0]
  z['artist_norm']=z.lead_artist.map(norm)
  z['platform']=platform
  if platform=='spotify':
   if not {'track_id','streams'}.issubset(z): raise ValueError('Spotify must include track_id and streams')
   z['item_id']=z.track_id
   z['visible_value']=pd.to_numeric(z.streams,errors='coerce')
   z['lead_artist_uri']=z.artist_uris.fillna('').astype(str).str.split(r'\s*\|\s*').str[0] if 'artist_uris' in z else ''
  else:
   if not {'key','views'}.issubset(z):raise ValueError('YouTube must include key and views')
   z['item_id']=z.key
   z['visible_value']=pd.to_numeric(z.views,errors='coerce')
   z['lead_artist_uri']=''
  chunks.append(z[['platform','week_end','rank','artist_norm','lead_artist','lead_artist_uri','item_id','title','visible_value']])
 out=pd.concat(chunks,ignore_index=True)
 out=out.drop_duplicates(['platform','week_end','item_id','rank'])
 return out


def event_visibility(reviews:pd.DataFrame,chart:pd.DataFrame,pre_weeks=8,post_weeks=8,lookback_weeks=52,blackout_weeks=8):
 if chart.platform.nunique()!=1:raise ValueError('Run one platform at a time')
 platform=chart.platform.iloc[0]
 unique_artists=chart[['artist_norm','lead_artist_uri']].drop_duplicates()
 # Disambiguate Spotify artist names by stable URI; YouTube lacks IDs in chart file.
 if platform=='spotify':
  n=unique_artists.groupby('artist_norm').lead_artist_uri.nunique()
  invalid=set(n[n>1].index)
 else:invalid=set()
 chart=chart[~chart.artist_norm.isin(invalid)]
 weekly=(chart.groupby(['artist_norm','week_end'],as_index=False)
         .agg(visible_items=('item_id','nunique'),visible_streams_or_views=('visible_value','sum')))
 calendar=pd.DatetimeIndex(sorted(chart.week_end.unique()))
 rows=[];week_rows=[]
 for r in reviews.itertuples(index=False):
  t=pd.to_datetime(r.pub_date)
  artist=norm(r.artist)
  pre=calendar[calendar<t][-pre_weeks:]
  post=calendar[calendar>=t][:post_weeks]
  # ensure each period spans exactly the expected number of consecutive weekly timestamps
  pre_valid=len(pre)==pre_weeks and np.all(np.diff(pre).astype('timedelta64[D]').astype(int)==7)
  post_valid=len(post)==post_weeks and np.all(np.diff(post).astype('timedelta64[D]').astype(int)==7)
  gap_end=t-pd.Timedelta(weeks=blackout_weeks)
  lag=calendar[calendar<gap_end][-lookback_weeks:]
  lag_valid=len(lag)==lookback_weeks and np.all(np.diff(lag).astype('timedelta64[D]').astype(int)==7)
  artistweeks=weekly[weekly.artist_norm==artist].set_index('week_end')
  # A zero means absent from an OBSERVED chart, not zero playback.
  def lookup(d):
   return (float(artistweeks.loc[d,'visible_streams_or_views']),int(artistweeks.loc[d,'visible_items'])) if d in artistweeks.index else (0.0,0)
  record={'reviewid':r.reviewid,'platform':platform,'chart_valid_window':bool(pre_valid and post_valid),
          'prior_chart_lookback_valid':bool(lag_valid),
          'identity_ambiguous':artist in invalid,'prior_chart_visible_weeks':np.nan,
          'prior_chart_visible_value':np.nan,'prior_chart_visible_share':np.nan,
          'pre_chart_visible_share':np.nan,'post_chart_visible_share':np.nan,
          'pre_chart_visible_value':np.nan,'post_chart_visible_value':np.nan}
  if lag_valid and artist not in invalid:
   vals=[lookup(d) for d in lag]
   record.update(prior_chart_visible_weeks=sum(v[1]>0 for v in vals),
                 prior_chart_visible_share=np.mean([v[1]>0 for v in vals]),
                 prior_chart_visible_value=sum(v[0] for v in vals))
  if pre_valid and post_valid and artist not in invalid:
   for label,dates in [('pre',pre),('post',post)]:
    vals=[lookup(d) for d in dates]
    record[f'{label}_chart_visible_share']=float(np.mean([v[1]>0 for v in vals]))
    record[f'{label}_chart_visible_value']=float(np.mean([v[0] for v in vals]))
    for ii,(d,(stream,n_items)) in enumerate(zip(dates,vals)):
     week_rows.append({'reviewid':r.reviewid,'platform':platform,'period':label,
                       'event_week':ii-(pre_weeks-1) if label=='pre' else ii+1,
                       'week_end':d,'visible_value':stream,'visible_items':n_items,
                       'charted':int(n_items>0)})
  rows.append(record)
 return pd.DataFrame(rows),pd.DataFrame(week_rows)
