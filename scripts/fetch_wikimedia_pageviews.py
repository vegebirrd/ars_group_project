#!/usr/bin/env python3
"""Optional API fetch from a *manually confirmed* title manifest.

Preserves API responses and error status; missing views never replaced by 0.
This is a collector, not a full artist identity matching pipeline.
"""
from __future__ import annotations
import argparse,json,time,urllib.parse,datetime
from pathlib import Path
import requests,pandas as pd

BASE='https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article'

def url_for(title,start,end):
    return f'{BASE}/en.wikipedia.org/all-access/user/{urllib.parse.quote(str(title).replace(" ","_"),safe="()")}/daily/{start}/{end}'

def fetch(manifest,output,delay=1.0,timeout=40):
    output.mkdir(parents=True,exist_ok=True)
    statuses=[]
    http=requests.Session()
    http.headers['User-Agent']='ARS-Music-Criticism/1.0 (research; source credit in README)'
    for _,row in manifest.iterrows():
        rid=str(row.reviewid)
        url=url_for(row.wiki_title,row.start,row.end)
        target=output/f'{rid}.json'
        try:
            resp=http.get(url,timeout=timeout)
            resp.raise_for_status()
            payload=resp.json()
            items=payload.get('items',[])
            dates={i.get('timestamp','')[:8] for i in items if i.get('views') is not None}
            status={'reviewid':rid,'status':'complete' if len(dates)==113 else 'incomplete',
                    'observed_days':len(dates),'http_status':resp.status_code,
                    'source_url':url,'wiki_title':row.wiki_title}
            # Persist successful raw JSON even when days are incomplete for audit.
            target.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
        except requests.RequestException as exc:
            status={'reviewid':rid,'status':'request_error','observed_days':None,
                    'http_status':getattr(getattr(exc,'response',None),'status_code',None),
                    'source_url':url,'wiki_title':row.wiki_title,'error':str(exc)}
        statuses.append(status)
        pd.DataFrame(statuses).to_csv(output/'fetch_status.csv',index=False)
        time.sleep(max(float(delay),0))
    print(f'Processed {len(statuses)} pageview requests; complete={sum(s["status"]=="complete" for s in statuses)}.')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--delay',type=float,default=1.0)
    a=p.parse_args()
    manifest=pd.read_csv(a.manifest,dtype={'start':str,'end':str,'reviewid':str})
    required={'reviewid','wiki_title','start','end'}
    if not required.issubset(manifest.columns):raise ValueError(required-set(manifest.columns))
    fetch(manifest,a.output,delay=a.delay)
if __name__=='__main__':main()
