#!/usr/bin/env python3
"""Make manual artist/album-to-video verification sheet for YouTube comments.

Choose a video whose subject genuinely matches the REVIEWED album; note uploader,
video publication date and reasons for selection. One review is NOT necessarily
one YouTube video; duplicate video IDs are allowed but audit before estimation.
"""
import argparse
from pathlib import Path
import pandas as pd

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reviews',default='data/processed/review_sample.csv')
    p.add_argument('--out',default='data/processed/youtube_video_manifest.csv')
    a=p.parse_args()
    source=pd.read_csv(a.reviews)
    needed=['reviewid','artist','title','pub_date']
    if set(needed)-set(source):p.error(f'Required fields missing: {sorted(set(needed)-set(source))}')
    frame=source[needed].drop_duplicates('reviewid').copy()
    frame['video_id']='';frame['video_title']='';frame['video_published_at']=''
    frame['video_match_reason']='';frame['verified_by']=''
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    frame.to_csv(a.out,index=False)
    print('Created verification manifest; fill video_id manually:',a.out)
if __name__=='__main__':main()
