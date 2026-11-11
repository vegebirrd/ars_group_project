"""Synthetic checks for no look-ahead, scores by year and chart calendar gaps."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np,pandas as pd
from src.extended_sampling import load_catalogue,prepare_catalogue,sample_by_year_score,career_pre_review_history
from scripts.collect_prior_popularity import calculate_prior_features
from src.modern_charts import read_weekly,event_visibility

def test_year_score_sampling_and_no_future_leak():
 rows=[]
 for year in (2022,2023):
  for score in (3.,6.,9.):
   for i in range(4):
    rows.append(dict(artist='Test Artist',title=f'{year}-{score}-{i}',date=f'{year}-06-{i+1:02d}',score=score,genre='Rock',bnm=False))
 # Exercise the source field adapter (date -> pub_date) as in The-Fork JSON.
 from tempfile import TemporaryDirectory
 import json
 with TemporaryDirectory() as td:
  source=Path(td)/'albums.json'
  source.write_text(json.dumps(rows))
  frame,excluded=prepare_catalogue(load_catalogue(source))
 assert len(frame)==24 and len(excluded)==0
 _,smpl=sample_by_year_score(frame,2022,2023,2,'seed')
 assert len(smpl)==12
 assert set(smpl.selection_probability)=={0.5}
 # For each row only earlier records older than the blackout are counted.
 history=career_pre_review_history(smpl,frame)
 for r in history.itertuples(index=False):
  assert r.prior_pitchfork_reviews==sum((frame.artist_norm==r.artist_norm)&
    (pd.to_datetime(frame.pub_date)<pd.to_datetime(r.pub_date)-pd.Timedelta(days=57)))

def test_wiki_popularity_uses_only_180_to_61():
 t=pd.Timestamp('2025-06-01');days=pd.date_range(t-pd.Timedelta(days=180),t-pd.Timedelta(days=61))
 observations=[{'timestamp':f'{d:%Y%m%d}00','views':10} for d in days]
 observations += [{'timestamp':f'{t:%Y%m%d}00','views':1_000_000}]
 z=calculate_prior_features(t,observations)
 assert z['prior_wiki_observed_days']==120
 assert z['prior_wiki_mean_views']==10
 z=calculate_prior_features(t,observations[:-20])
 assert np.isnan(z['prior_wiki_mean_views'])

def test_modern_chart_global_panel_and_prior_gap(tmp_path):
 path=tmp_path/'spotify_top200_positions_2024.csv.gz'
 dates=pd.date_range('2024-01-04',periods=70,freq='7D')
 d=pd.DataFrame([dict(cc='global',week_end=dt.date(),rank=1,artists='Artist A',title='Song',
                        artist_uris='spotify:artist:123',track_id='song123',streams=100,
                        ) for dt in dates])
 # Extra unrelated country row must not enter global chart totals.
 d=pd.concat([d,pd.DataFrame([dict(cc='us',week_end=dates[5].date(),rank=1,artists='Artist A',
   title='Song',artist_uris='spotify:artist:123',track_id='song123',streams=999999)])],ignore_index=True)
 d.to_csv(path,compression='gzip',index=False)
 c=read_weekly(tmp_path,'spotify'); assert len(c)==70
 pub=dates[62]+pd.Timedelta(days=1)
 reviews=pd.DataFrame([dict(reviewid='test1',artist='Artist A',pub_date=pub)])
 outcome,weeks=event_visibility(reviews,c)
 # 62 preceding chart weeks, but only seven after the event: incomplete post period.
 assert not outcome.iloc[0].chart_valid_window
 assert outcome.iloc[0].prior_chart_lookback_valid
 assert outcome.iloc[0].prior_chart_visible_weeks==52
 # A later complete post-window requires more chart weeks.
 d2=pd.DataFrame([dict(cc='global',week_end=dt.date(),rank=1,artists='Artist A',title='Song',
                        artist_uris='spotify:artist:123',track_id='song123',streams=100)
                  for dt in pd.date_range(dates[-1]+pd.Timedelta(days=7),periods=10,freq='7D')])
 pd.concat([d,d2]).to_csv(path,compression='gzip',index=False)
 outcome,weeks=event_visibility(reviews,read_weekly(tmp_path,'spotify'))
 assert outcome.iloc[0].chart_valid_window and len(weeks)==16
 assert outcome.iloc[0].pre_chart_visible_share==1
