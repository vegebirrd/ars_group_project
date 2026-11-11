#!/usr/bin/env python3
"""Global Spotify Top-200 weekly chart analysis from the publicly archived CSV.

Analytical units: review x chart week, then review event. Musician names matched
conservatively to a *unique* Spotify artist ID; ambiguous artists are exported for review.
Streams are the sum of visible charted tracks, not full-market sales or plays.
"""
from __future__ import annotations
import argparse,json,re,unicodedata
from pathlib import Path
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def norm(x):
    txt=unicodedata.normalize('NFKD',str(x)).casefold()
    txt=''.join(t for t in txt if not unicodedata.combining(t))
    return re.sub(r'[^a-z0-9]+',' ',txt).strip()

def read_charts(path):
    needed=['artist_id','artist_name','album_id','album_name','track_id','week','streams','rank']
    # The public archive uses semicolon delimiter; rows may repeat for collaborations.
    d=pd.read_csv(path,sep=';',usecols=needed,low_memory=False)
    d['chart_week']=pd.to_datetime(d.week,errors='coerce')
    d['streams']=pd.to_numeric(d.streams,errors='coerce')
    d['artist_norm']=d.artist_name.map(norm);d['album_norm']=d.album_name.map(norm)
    d=d.dropna(subset=['chart_week','streams','artist_id','track_id'])
    d=d.drop_duplicates(['artist_id','track_id','chart_week'])
    return d

def build(reviews,chart):
    r=reviews.copy();r['artist_norm']=r.artist.map(norm);r['album_norm']=r.title.map(norm)
    map_rows=chart[['artist_norm','artist_id']].drop_duplicates()
    counts=map_rows.groupby('artist_norm').artist_id.nunique()
    singles=counts[counts.eq(1)].index
    unique_map=map_rows[map_rows.artist_norm.isin(singles)].drop_duplicates('artist_norm')
    r=r.merge(unique_map,on='artist_norm',how='left',validate='many_to_one')
    r['identity_status']=np.where(r.artist_id.notna(),'unique_exact_name','not_unique_or_not_found')
    can=r[r.artist_id.notna()].copy()
    artistweeks=chart.groupby(['artist_id','chart_week'],as_index=False).agg(
        chart_tracks=('track_id','nunique'),charted_track_streams=('streams','sum'))
    albumweeks=chart.groupby(['artist_id','album_norm','chart_week'],as_index=False).agg(
        album_tracks=('track_id','nunique'),album_streams=('streams','sum'))
    calendar=pd.Series(chart.chart_week.unique()).sort_values().reset_index(drop=True)
    rows=[]
    for s in can.itertuples(index=False):
        date=pd.to_datetime(s.pub_date)
        prev=calendar[calendar<date].tail(8)
        after=calendar[calendar>=date].head(8)
        if len(prev)!=8 or len(after)!=8:continue
        for event_week,t in list(zip(range(-8,0),prev))+list(zip(range(1,9),after)):
            rows.append(dict(reviewid=s.reviewid,artist=s.artist,title=s.title,score=s.score,
                             artist_id=s.artist_id,album_norm=s.album_norm,
                             chart_week=pd.to_datetime(t),event_week=event_week))
    panel=pd.DataFrame(rows)
    if panel.empty:return r,panel,pd.DataFrame()
    panel=panel.merge(artistweeks,on=['artist_id','chart_week'],how='left',validate='many_to_one')
    panel=panel.merge(albumweeks,on=['artist_id','album_norm','chart_week'],how='left',validate='many_to_one')
    panel['artist_top200_visible']=(panel.chart_tracks.notna()).astype(int)
    panel['album_top200_visible']=(panel.album_tracks.notna()).astype(int)
    # Visible chart streams in a non-chart week can be recorded as zero ONLY for
    # the chart-visible statistic; not interpreted as actual total plays.
    for col in ['chart_tracks','charted_track_streams','album_tracks','album_streams']:
        panel[col]=panel[col].fillna(0)
    ev=[]
    for rid,g in panel.groupby('reviewid'):
        pre=g[g.event_week<0];post=g[g.event_week>0]
        if len(pre)!=8 or len(post)!=8:continue
        ev.append(dict(reviewid=rid,artist=g.artist.iloc[0],title=g.title.iloc[0],score=g.score.iloc[0],
             artist_id=g.artist_id.iloc[0],pre_artist_visible=pre.artist_top200_visible.mean(),
             post_artist_visible=post.artist_top200_visible.mean(),
             presence_delta=post.artist_top200_visible.mean()-pre.artist_top200_visible.mean(),
             pre_album_visible=pre.album_top200_visible.mean(),post_album_visible=post.album_top200_visible.mean(),
             album_presence_delta=post.album_top200_visible.mean()-pre.album_top200_visible.mean(),
             pre_album_visible_streams=pre.album_streams.mean(),post_album_visible_streams=post.album_streams.mean()))
    return r,panel,pd.DataFrame(ev)

def make_figures(panel,summary,figdir):
    figdir.mkdir(parents=True,exist_ok=True)
    w=panel.groupby('event_week',as_index=False).agg(artist_share=('artist_top200_visible','mean'),album_share=('album_top200_visible','mean'))
    w.to_csv(figdir.parent/'RQ1_spotify_weekly_trajectory.csv',index=False)
    fig,ax=plt.subplots(figsize=(8.5,4.5))
    ax.plot(w.event_week,w.artist_share,marker='o',label='Artist in Global Top 200')
    ax.plot(w.event_week,w.album_share,marker='s',label='Reviewed album has charted tracks')
    ax.axvline(0,color='gray',ls=':');ax.set(title='Spotify chart visibility near review',xlabel='Chart weeks relative to review',ylabel='Visible share',ylim=(0,1));ax.legend(frameon=False)
    fig.tight_layout();fig.savefig(figdir/'09_spotify_chart_visibility.png',dpi=170);plt.close(fig)
    if len(summary):
        summary['score_group']=pd.cut(summary.score,[-.00001,5,8,10.00001],labels=['Low','Middle','High'],right=False)
        stats=summary.groupby('score_group',observed=True)[['presence_delta','album_presence_delta']].mean()
        fig,ax=plt.subplots(figsize=(7.5,4.2));stats.plot.bar(ax=ax)
        ax.set(xlabel='Score group',ylabel='Mean post-minus-pre chart visibility',title='Spotify chart visibility by review score');ax.axhline(0,color='gray',lw=.6)
        fig.tight_layout();fig.savefig(figdir/'10_spotify_by_score.png',dpi=170);plt.close(fig)

def main():
    p=argparse.ArgumentParser();p.add_argument('--reviews',type=Path,default=Path('data/processed/eligible_reviews.csv'))
    p.add_argument('--charts',type=Path,default=Path('data/downloads/spotify/spotify-top-200-dataset.csv'))
    p.add_argument('--out',type=Path,default=Path('outputs'))
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    chart=read_charts(a.charts);r,panel,summary=build(pd.read_csv(a.reviews),chart)
    r.to_csv(a.out/'spotify_artist_matching_audit.csv',index=False)
    panel.to_csv(a.out/'spotify_chart_week_panel.csv',index=False)
    summary.to_csv(a.out/'spotify_review_summary.csv',index=False)
    if len(panel):make_figures(panel,summary,a.out/'figures')
    report={'review_events':int(len(r)),'unique_artist_id_match':int(r.artist_id.notna().sum()),
            'events_with_complete_chart_calendar':int(len(summary)),
            'pre_artist_visibility':float(summary.pre_artist_visible.mean()) if len(summary) else None,
            'post_artist_visibility':float(summary.post_artist_visible.mean()) if len(summary) else None,
            'pre_album_visibility':float(summary.pre_album_visible.mean()) if len(summary) else None,
            'post_album_visibility':float(summary.post_album_visible.mean()) if len(summary) else None}
    (a.out/'spotify_summary.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
