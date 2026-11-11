"""End-to-end tests for the public code; all observations generated in memory."""
import json
import numpy as np
import pandas as pd
from scripts.prepare_reviews import build
from scripts.build_event_panel import build as build_panel
from src.online_analysis import run, data_transform, fit_cluster
from src.spotify_from_downloads import build as chart_build, read_charts


def demo_reviews():
    return pd.DataFrame({
        'artist':['Alpha','Beta','Alpha','Gamma','Dora','Ezra','Foo','Bar'],
        'album':['A','B','A','C','D','E','F','G'],
        'reviewdate':['January 2 2018','February 2 2018','January 2 2018','March 3 2018','April 1 2018','May 5 2018','June 6 2018','July 7 2018'],
        'score':[2.5,7.0,2.5,9,8.5,4.3,6.8,7.3],
        'genre':['Rock','Pop','Rock','Rap','Pop','Rap','Rock','Jazz']})


def fake_data(n=26):
    rng=np.random.default_rng(2)
    events=[];rows=[]
    for k in range(n):
        score=2.5+(k%10)*.7
        date=pd.Timestamp('2018-06-15')+pd.Timedelta(days=k*13)
        events.append({'reviewid':f'r{k:03}', 'pub_date':date.strftime('%Y-%m-%d'),
                       'score':score,'artist':f'Artist {k}','title':f'Album {k}',
                       'wiki_wikipedia_title':f'Artist_{k//2}', 'genre':['Rock','Pop','Rap'][k%3],
                       'musicbrainz_release_to_review_days':k%15-3})
        for tau in range(-56,57):
            shift=.15*np.sin((tau+k)*.11)
            views=max(0,int(np.expm1(4.2+.012*tau+(tau>=0)*((score-7)*.07)+shift+rng.normal(0,.13))))
            rows.append({'reviewid':f'r{k:03}','date':(date+pd.Timedelta(days=tau)).strftime('%Y-%m-%d'),
                         'event_day':tau,'views':views,'observed':1})
    return pd.DataFrame(events),pd.DataFrame(rows)

def test_review_preparation_sampling_and_duplicates():
    full,samp,duplicates=build(demo_reviews(),2018,2019,2)
    assert len(full)==7 and len(duplicates)==1
    assert len(samp)<=6
    assert full.reviewid.iloc[0]=='p4k_00000001'
    assert (full.pub_date.str[:4]=='2018').all()

def test_panel_build_and_missingness(tmp_path):
    fake=pd.DataFrame({'reviewid':['r1','r2'],'pub_date':['2018-01-15','2018-01-22'],'wiki_wikipedia_title':['A','B']})
    days=pd.date_range('2017-11-20','2018-03-12')
    (tmp_path/'r1.json').write_text(json.dumps({'items':[{'timestamp':d.strftime('%Y%m%d')+'00','views':7} for d in days]}))
    panel,complete,cover=build_panel(fake,tmp_path)
    assert len(panel)==226 and len(complete)==1 and cover.observed_days.tolist()==[113,0]
    assert int(panel.loc[panel.reviewid=='r2','observed'].sum())==0

def test_all_attention_regressions_and_figures(tmp_path):
    a,b=fake_data()
    ev,day,ab=data_transform(a,b)
    assert len(ev)==26 and len(day)==26*113
    assert {'abnormal_post7','abnormal_pre7','increment','short_abs_delta','release_lag'}.issubset(ev.columns)
    fit,table=fit_cluster(ev,'short_delta',['x','baseline','trend_week'])
    assert fit is not None and table.term.eq('x').any()
    manifest=run(a,b,tmp_path/'results')
    assert manifest['n_events']==26
    assert (tmp_path/'results/RQ1_regressions.csv').exists()
    assert (tmp_path/'results/RQ2_heterogeneity.csv').exists()
    assert len(list((tmp_path/'results/figures').glob('*.png')))>=7

def test_spotify_chart_matching_and_periods(tmp_path):
    d=[]
    for w in pd.date_range('2018-01-05',periods=40,freq='7D'):
        d.append({'artist_id':'ID1','artist_name':'Example','album_id':'AL1', 'album_name':'The Release',
                  'track_id':'TRACK1','week':w.strftime('%m/%d/%Y'),'streams':2000,'rank':15})
    p=tmp_path/'chart.csv';pd.DataFrame(d).to_csv(p,sep=';',index=False)
    chart=read_charts(p)
    reviews=pd.DataFrame({'reviewid':['x'],'artist':['Example'],'title':['The Release'],'pub_date':['2018-05-11'],'score':[9]})
    mapping,panel,out=chart_build(reviews,chart)
    assert len(panel)==16 and len(out)==1
    assert out.pre_artist_visible.iloc[0]==1 and out.post_album_visible.iloc[0]==1
