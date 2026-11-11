#!/usr/bin/env python3
"""Spotify *album-specific, chart-visible* track streams; not album sales.
Original archive: spotify Top 200 global weekly chart. Exact normalized album title
and resolved Spotify artist ID, with flagged identity uncertainty.
"""
from pathlib import Path
import zipfile, argparse, io, re, unicodedata, json
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def norm(s):
    q=unicodedata.normalize('NFKD',str(s)).casefold()
    q=''.join(k for k in q if not unicodedata.combining(k))
    return re.sub(r'[^a-z0-9]+',' ',q).strip()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,default=Path('.'));ap.add_argument('--data-zip',type=Path,default=Path('/mnt/data/data.zip'))
    a=ap.parse_args();base=a.base;out=base/'results'/'album_charts';figs=out/'figures';figs.mkdir(parents=True,exist_ok=True)
    cols=['week_end','artist_id','album_name','album_id','track_id','streams','artist_name']
    local_csv=base/'inputs/data/processed/spotify/artist_track_weekly.csv'
    if local_csv.exists():
        track=pd.read_csv(local_csv,usecols=cols)
    else:
        with zipfile.ZipFile(a.data_zip) as z:
            track=pd.read_csv(z.open('data/processed/spotify/artist_track_weekly.csv'),usecols=cols)
    track['album_norm']=track.album_name.map(norm)
    # Resolve exact album and artist matches; retain unique track row per week.
    tr=track.sort_values('streams',ascending=False).drop_duplicates(['week_end','artist_id','album_norm','track_id'])
    tragg=tr.groupby(['artist_id','album_norm','week_end'],as_index=False).agg(
        charted_album_streams=('streams','sum'),charted_album_tracks=('track_id','nunique'),
        spotify_album_id_count=('album_id','nunique'),spotify_album_ids=('album_id',lambda x:';'.join(sorted(set(x.astype(str)))))
    )
    sp=pd.read_csv(base/'processed/spotify_cohort_analysis.csv')
    sp['album_norm']=sp.title.map(norm)
    sp=sp[['reviewid','artist','title','pub_date','score','spotify_artist_id','album_norm','identity_status','mb_spotify_corroborated']].copy()
    tralbum=tragg[['artist_id','album_norm']].drop_duplicates()
    sp['album_ever_in_track_archive']=(sp.merge(tralbum,how='left',left_on=['spotify_artist_id','album_norm'],right_on=['artist_id','album_norm'])['artist_id'].notna().to_numpy()).astype(int)
    periods=pd.read_csv(base/'inputs/data/extension_20261022/processed/spotify/review_weekly_panel.csv')
    periods=periods[periods.alignment=='boundary_friday'][['reviewid','event_week','chart_label','calendar_complete_top200']].copy()
    p=sp.merge(periods,on='reviewid',validate='one_to_many')
    p=p.merge(tragg,how='left',left_on=['spotify_artist_id','album_norm','chart_label'],right_on=['artist_id','album_norm','week_end'],validate='many_to_one')
    p['album_top200_present']=(p.charted_album_tracks.fillna(0)>0).astype(int)
    p['album_top200_streams_observed']=p.charted_album_streams.fillna(0).astype(float)
    p['charted_album_tracks']=p.charted_album_tracks.fillna(0).astype(int)
    p.to_csv(out/'album_specific_event_week.csv',index=False)
    vals=[]
    for rid,d in p.groupby('reviewid'):
        obs=d[(d.event_week.between(-8,-1)) | (d.event_week.between(1,8))]
        a=obs[obs.event_week.between(-8,-1)]
        b=obs[obs.event_week.between(1,8)]
        # Only calendar-complete windows can be summarized (not zero-fill missing charts).
        if len(a)!=8 or len(b)!=8 or not obs.calendar_complete_top200.eq(1).all():
            continue
        rr=d.iloc[0]
        vals.append(dict(reviewid=rid,artist=rr.artist,title=rr.title,score=rr.score,
            identity_status=rr.identity_status,mb_spotify_corroborated=rr.mb_spotify_corroborated,
            album_ever_in_track_archive=int(rr.album_ever_in_track_archive),
            album_charted_in_event_window=int(d.album_top200_present.sum()>0),
            pre_alb_charted_weeks=int(a.album_top200_present.sum()),post_alb_charted_weeks=int(b.album_top200_present.sum()),
            pre_album_top200_streams_total=float(a.album_top200_streams_observed.sum()),
            post_album_top200_streams_total=float(b.album_top200_streams_observed.sum()),
            pre_album_top200_streams_weekly=float(a.album_top200_streams_observed.mean()),
            post_album_top200_streams_weekly=float(b.album_top200_streams_observed.mean()),
            post_minus_pre_album_visible_streams=float(b.album_top200_streams_observed.mean()-a.album_top200_streams_observed.mean())))
    ev=pd.DataFrame(vals)
    ev.to_csv(out/'album_specific_event_summary.csv',index=False)
    eligible=ev[ev.album_ever_in_track_archive.eq(1)]
    result=dict(n_review_cohort=len(sp),n_calendar_eligible=len(ev),n_ever_album_match=int(ev.album_ever_in_track_archive.sum()),
                n_album_visible_in_window=int(ev.album_charted_in_event_window.sum()),
                n_MB_spotify_verified=int(pd.to_numeric(eligible.mb_spotify_corroborated,errors='coerce').eq(1).sum()),
                pre_album_top200_present_share=float((eligible.pre_alb_charted_weeks>0).mean()),
                post_album_top200_present_share=float((eligible.post_alb_charted_weeks>0).mean()),
                mean_pre_visible_streams=float(eligible.pre_album_top200_streams_weekly.mean()),
                mean_post_visible_streams=float(eligible.post_album_top200_streams_weekly.mean()),
                n_post_album_visible=int((eligible.post_alb_charted_weeks>0).sum()),
                n_pre_album_visible=int((eligible.pre_alb_charted_weeks>0).sum()),
                archive_warning='Track-level Spotify Global Top 200 streams only; 0 means not in Top 200, never 0 actual consumption.' )
    (out/'summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    curve=p[p.album_ever_in_track_archive.eq(1)].groupby('event_week',as_index=False).agg(
        artist_album_top200_present=('album_top200_present','mean'),
        mean_observed_album_streams=('album_top200_streams_observed','mean'),n=('reviewid','size'))
    curve.to_csv(out/'album_curve.csv',index=False)
    fig,ax=plt.subplots(figsize=(9,4.6))
    ax.plot(curve.event_week,curve.artist_album_top200_present,marker='o',lw=1.8)
    ax.axvline(0,ls=':',color='gray');ax.set(title='Reviewed-album tracks visible in Spotify Global Top 200',xlabel='Chart weeks relative to review',ylabel='Fraction with at least one charted track',ylim=(0,1))
    fig.tight_layout();fig.savefig(figs/'album_top200_visibility.png',dpi=200);plt.close(fig)
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
