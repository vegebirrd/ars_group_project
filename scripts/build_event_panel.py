#!/usr/bin/env python3
"""Raw Wikimedia API JSON -> exact-day event panel and complete-window sample."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

def build(reviews:pd.DataFrame,raw_dir:Path):
    all_rows=[];summary=[]
    for e in reviews.itertuples(index=False):
        t0=pd.to_datetime(e.pub_date)
        path=raw_dir/f'{e.reviewid}.json'
        try:
            d=json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
            items=d.get('items',[]) or []
            dates={pd.to_datetime(str(i['timestamp'])[:8],format='%Y%m%d'):i['views'] for i in items if i.get('views') is not None and i.get('timestamp')}
        except (ValueError,KeyError,TypeError,json.JSONDecodeError):dates={}
        days=pd.date_range(t0-pd.Timedelta(days=56),t0+pd.Timedelta(days=56),freq='D')
        observed=sum(int(day in dates) for day in days)
        for j,day in enumerate(days):
            v=dates.get(day)
            all_rows.append({'reviewid':e.reviewid,'event_day':j-56,'date':day.strftime('%Y-%m-%d'),'views':v,
                             'observed':int(day in dates),'wiki_title':getattr(e,'wiki_wikipedia_title',None)})
        summary.append({'reviewid':e.reviewid,'observed_days':observed,'full_window':int(observed==113)})
    panel=pd.DataFrame(all_rows)
    quality=pd.DataFrame(summary)
    sample=reviews.merge(quality,on='reviewid',validate='one_to_one')
    sample=sample[sample.full_window==1].copy()
    return panel, sample, quality

def main():
    p=argparse.ArgumentParser();p.add_argument('--reviews',type=Path,default=Path('data/processed/review_enriched.csv'))
    p.add_argument('--json-dir',type=Path,default=Path('data/raw/wikipedia'))
    p.add_argument('--out',type=Path,default=Path('data/processed'))
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    panel,sample,quality=build(pd.read_csv(a.reviews),a.json_dir)
    panel.to_csv(a.out/'pageview_panel.csv',index=False)
    sample.to_csv(a.out/'attention_complete_sample.csv',index=False)
    quality.to_csv(a.out/'pageview_coverage.csv',index=False)
    print(f'Event panel {len(panel):,} rows; full 113-day windows {len(sample):,}; coverage {len(quality):,} candidate events.')
if __name__=='__main__':main()
