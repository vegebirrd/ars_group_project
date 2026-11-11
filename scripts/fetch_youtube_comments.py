#!/usr/bin/env python3
"""Collect top-level public YouTube comments via the official YouTube Data API.

Required manually verified manifest columns: reviewid, video_id, pub_date.
Set YOUTUBE_API_KEY in environment (not committed to Git). PublishedAt is
comment time; results are a CURRENT snapshot of still-accessible comments.
Default --max-pages is intentionally small and caps sampled recent comments.
"""
from __future__ import annotations
import argparse, json, os, re, sys, time
from pathlib import Path
import pandas as pd
import requests
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.text_research import extract_comment_rows,summarize_comments
API='https://www.googleapis.com/youtube/v3/commentThreads'
VIDEO_ID=re.compile(r'^[A-Za-z0-9_-]{11}$')

def api_fetch(session, video_id, token, api_key):
    params=dict(part='snippet',videoId=video_id,maxResults=100,
                textFormat='plainText',order='time',key=api_key)
    if token:params['pageToken']=token
    r=session.get(API,params=params,timeout=30)
    if r.status_code!=200:
        raise RuntimeError(f'YouTube HTTP {r.status_code}: {r.text[:250]}')
    return r.json()

def fetch_video(session,record,api_key,max_pages=3,pause=0.3):
    rows=[];pages=0;token=None;last_payload={};status='ok'
    while pages<max_pages:
        obj=api_fetch(session,record.video_id,token,api_key)
        rows+=extract_comment_rows(obj,record.video_id,record.reviewid,record.pub_date)
        pages+=1;last_payload=obj
        token=obj.get('nextPageToken')
        if not token:break
        time.sleep(pause)
    truncated=bool(token)
    return rows,dict(reviewid=str(record.reviewid),video_id=str(record.video_id),
                    pages_fetched=pages, top_level_comments_fetched=len(rows),
                    truncated=int(truncated), collection_status=status)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',default='data/processed/youtube_video_manifest.csv')
    p.add_argument('--out-dir',default='data/processed')
    p.add_argument('--max-pages',type=int,default=3)
    p.add_argument('--pause',type=float,default=0.3)
    a=p.parse_args()
    key=os.environ.get('YOUTUBE_API_KEY','').strip()
    if not key:p.error('Set YOUTUBE_API_KEY environment variable (Google Cloud / YouTube Data API v3)')
    if a.max_pages<1 or a.max_pages>100:p.error('max-pages must be 1..100')
    manifest=pd.read_csv(a.manifest,dtype=str).fillna('')
    missing={'reviewid','video_id','pub_date'}-set(manifest)
    if missing:p.error('Missing manifest fields: '+str(sorted(missing)))
    manifest=manifest[manifest.video_id.str.fullmatch(VIDEO_ID.pattern)].copy()
    if manifest.empty:p.error('No verified 11-character video_id in manifest')
    if any(manifest.duplicated(['reviewid','video_id'])):
        p.error('Duplicate reviewid, video_id pairs in manifest')
    out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
    all_rows=[];audit=[]
    with requests.Session() as sess:
        for rec in manifest.itertuples(index=False):
            try:
                rows,info=fetch_video(sess,rec,key,a.max_pages,a.pause)
                all_rows.extend(rows)
                audit.append(info)
                print(f'{rec.reviewid} / {rec.video_id}: {len(rows)} current comments, {info["pages_fetched"]} pages')
            except Exception as e:
                audit.append(dict(reviewid=str(rec.reviewid),video_id=str(rec.video_id),
                     pages_fetched=0, top_level_comments_fetched=0,truncated=0,
                     collection_status='error: '+str(e)[:200]))
                print('Warning:',rec.reviewid,str(e),file=sys.stderr)
            time.sleep(a.pause)
    columns=['reviewid','video_id','comment_id','published_date','event_day','text','like_count']
    comments=pd.DataFrame(all_rows,columns=columns)
    # Text is stored locally in raw folder, never in Git.
    raw=Path('data/raw/youtube');raw.mkdir(parents=True,exist_ok=True)
    comments.to_csv(raw/'comments_local.csv',index=False)
    daily,event=summarize_comments(comments)
    daily.to_csv(out/'youtube_comment_daily.csv',index=False)
    event.to_csv(out/'youtube_comment_event.csv',index=False)
    pd.DataFrame(audit).to_csv(out/'youtube_collection_audit.csv',index=False)
    print('Wrote numeric daily and event summaries plus collection audit')
if __name__=='__main__':main()
