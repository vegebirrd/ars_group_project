#!/usr/bin/env python3
"""Global 2020–25 Spotify+YouTube weekly chart visibility: pre and post review.

No chart-level statistic is a proxy for full album unit sales. Outcome: charted
song visibility and summed streams/views only, with published chart censoring.
"""
import argparse,sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.modern_charts import read_weekly,event_visibility

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--reviews',type=Path,default=Path('data/processed/review_sample.csv'))
 p.add_argument('--charts-dir',type=Path,default=Path('data/downloads/charts-modern'))
 p.add_argument('--out',type=Path,default=Path('data/processed/popularity'))
 a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 reviews=pd.read_csv(a.reviews)
 for platform in ('spotify','youtube'):
  d=read_weekly(a.charts_dir/platform,platform)
  outcome,week=event_visibility(reviews,d)
  outcome.to_csv(a.out/f'{platform}_modern_event_chart_metrics.csv',index=False)
  week.to_csv(a.out/f'{platform}_modern_event_chart_week.csv',index=False)
  print(platform, 'events',len(outcome),'charted complete',outcome.chart_valid_window.sum(),
        'lookback complete',outcome.prior_chart_lookback_valid.sum())
if __name__=='__main__':main()
