#!/usr/bin/env python3
"""Historical PRE-review Wikipedia popularity, using t-180...t-61 days.

Only research-approved artist page identifiers are queried. Each API response is
cached locally, and missing days are kept missing. The source is the Wikipedia
Analytics user-agent-filtered pageviews endpoint (2015-present).
"""
from __future__ import annotations
import argparse,json,time,urllib.parse,datetime
from pathlib import Path
import numpy as np,pandas as pd,requests

API='https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article'

def pageview_url(title,start,end):
    ident=urllib.parse.quote(title.replace(' ','_'),safe='()')
    return f'{API}/en.wikipedia.org/all-access/user/{ident}/daily/{start:%Y%m%d}00/{end:%Y%m%d}00'


def calculate_prior_features(pub_date,items,min_coverage=0.9):
    date=pd.to_datetime(pub_date).normalize()
    start=date-pd.Timedelta(days=180);end=date-pd.Timedelta(days=61)
    dates=pd.date_range(start,end)
    valid={pd.to_datetime(str(row.get('timestamp',''))[:8],format='%Y%m%d',errors='coerce'):row.get('views')
           for row in items if row.get('timestamp') and row.get('views') is not None}
    vals=np.array([valid.get(dt,np.nan) for dt in dates],dtype=float)
    available=np.isfinite(vals)
    result={'prior_wiki_observed_days':int(available.sum()),'prior_wiki_expected_days':len(dates),
            'prior_wiki_coverage':float(available.mean()),'prior_wiki_mean_views':np.nan,
            'prior_wiki_log_mean':np.nan,'prior_wiki_median_views':np.nan,
            'prior_wiki_weekly_trend':np.nan, 'prior_wiki_cv':np.nan}
    if available.mean()<min_coverage:return result
    v=vals[available];log=np.log1p(v)
    result.update(prior_wiki_mean_views=float(v.mean()),prior_wiki_median_views=float(np.median(v)),
                  prior_wiki_log_mean=float(log.mean()),prior_wiki_cv=float(v.std()/v.mean()) if v.mean() else np.nan,
                  prior_wiki_weekly_trend=float(np.polyfit(np.arange(len(vals))[available],log,1)[0]*7))
    return result


def query_pages(reviews, out_dir, email, delay=1.1):
    out_dir.mkdir(parents=True,exist_ok=True)
    client=requests.Session();client.headers.update({'User-Agent':f'ARS-prepopularity/1.0 (research contact {email})'})
    records=[]
    for idx,r in reviews.iterrows():
        rid=str(r.reviewid); date=pd.to_datetime(r.pub_date,errors='coerce'); title=r.get('wiki_wikipedia_title')
        row={'reviewid':rid,'prior_wiki_page_title':title,'prior_wiki_status':'no_title_or_date'}
        if pd.notna(date) and isinstance(title,str) and title.strip():
            start=date-pd.Timedelta(days=180);end=date-pd.Timedelta(days=61)
            cache=out_dir/'cache'/f'{rid}.json';cache.parent.mkdir(exist_ok=True)
            try:
                if cache.exists():payload=json.loads(cache.read_text())
                else:
                    url=pageview_url(title,start,end)
                    response=client.get(url,timeout=40);response.raise_for_status()
                    payload=response.json()
                    cache.write_text(json.dumps(payload,ensure_ascii=False))
                    time.sleep(max(1.0,delay))
                row.update(calculate_prior_features(date,payload.get('items',[])))
                row['prior_wiki_status']='complete' if row['prior_wiki_coverage']>=0.9 else 'partial'
            except (requests.RequestException, ValueError) as exc:
                row['prior_wiki_status']='error';row['prior_wiki_error']=str(exc)[:250]
        records.append(row)
        if (idx+1)%20==0:print(f'Prior popularity {idx+1}/{len(reviews)}',flush=True)
        pd.DataFrame(records).to_csv(out_dir/'prior_wikipedia_popularity.csv',index=False)
    return pd.DataFrame(records)


def main():
    p=argparse.ArgumentParser();p.add_argument('--reviews',type=Path,default=Path('data/processed/review_enriched.csv'))
    p.add_argument('--out',type=Path,default=Path('data/processed/popularity'))
    p.add_argument('--email',required=True);p.add_argument('--delay',type=float,default=1.1)
    a=p.parse_args()
    d=pd.read_csv(a.reviews).reset_index(drop=True)
    query_pages(d,a.out,a.email,a.delay)
    print('Saved:',a.out/'prior_wikipedia_popularity.csv')
if __name__=='__main__':main()
