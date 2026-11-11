"""Construct a modern Pitchfork review frame with pre-specified year/score sampling.

The-Fork's albums.json is a research discovery source, not an official Pitchfork
archive. We retain source identifiers and score/date validity flags. Reissue reviews
are tagged but NOT silently excluded. No article bodies are redistributed.
"""
from __future__ import annotations
import hashlib
import json
import re
import unicodedata
from pathlib import Path
import pandas as pd


def normalize(x: object) -> str:
    return ' '.join(unicodedata.normalize('NFKC', str(x or '')).casefold().split())


def _first(d: dict, names: tuple[str,...]):
    for n in names:
        v=d.get(n)
        if v is not None and str(v).strip() not in ('','None','nan'):
            return v
    return None


def _genres(x):
    if isinstance(x,list):return '|'.join(map(str,x))
    if isinstance(x,dict):return '|'.join(map(str,x.values()))
    return str(x or '')


def load_catalogue(path: Path) -> pd.DataFrame:
    if path.suffix.lower()=='.csv':
        rows=pd.read_csv(path).to_dict('records')
    else:
        data=json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data,list):rows=data
        elif isinstance(data,dict):
            rows=next((data[k] for k in ('albums','reviews','items','data') if isinstance(data.get(k),list)),None)
            if rows is None: raise ValueError('Unknown JSON layout: expected list of albums, reviews, items, or data')
        else:raise ValueError('Unsupported catalogue format')
    result=[]
    for i,row in enumerate(rows):
        if not isinstance(row,dict): continue
        art=_first(row,('artist','artistName','artist_name'))
        title=_first(row,('title','album','albumName','album_name'))
        date=_first(row,('date','reviewdate','review_date','pub_date','publish_date','published_at'))
        url=_first(row,('url','review_url','link'))
        score=_first(row,('score','rating'))
        genre=_first(row,('genres','genre'))
        record={'artist':art,'title':title,'pub_date':date,'score':score,
                'review_url':url,'genres_json':_genres(genre),
                'bnm':bool(row.get('bnm',False)),'bnr':bool(row.get('bnr',False)),
                'release_year_reported':_first(row,('year','releaseYear','year_released')),
                'source_record_id':_first(row,('id','reviewid')) or f'catalogue_{i}',
                'source_row':i}
        result.append(record)
    return pd.DataFrame(result)


def prepare_catalogue(frame: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    d=frame.copy()
    d['score']=pd.to_numeric(d['score'],errors='coerce')
    d['pub_date']=pd.to_datetime(d['pub_date'],errors='coerce',utc=True).dt.tz_convert(None).dt.normalize()
    d['artist']=d['artist'].astype('string').str.strip()
    d['title']=d['title'].astype('string').str.strip()
    d['year']=d['pub_date'].dt.year
    d['artist_norm']=d['artist'].fillna('').map(normalize)
    d['title_norm']=d['title'].fillna('').map(normalize)
    d['source_valid']=(d['year'].notna() & d['score'].between(0,10) &
                       d['artist_norm'].str.len().gt(0)&d['title_norm'].str.len().gt(0))
    failures=d[~d['source_valid']].copy()
    d=d[d['source_valid']].copy()
    d['pub_date']=d['pub_date'].dt.strftime('%Y-%m-%d')
    d['dedupe_key']=d['artist_norm']+'|'+d['title_norm']+'|'+d['pub_date']
    d=d.sort_values(['dedupe_key','review_url'],na_position='last')
    duplicates=d[d.duplicated('dedupe_key',keep='first')].copy()
    d=d.drop_duplicates('dedupe_key',keep='first').copy()
    d['reviewid']=d['dedupe_key'].map(lambda x: 'modern_'+hashlib.sha256(x.encode()).hexdigest()[:20])
    d['score_stratum']=pd.cut(d.score,[-0.00001,5,8,10.0001],right=False,labels=['low','middle','high']).astype(str)
    return d.sort_values(['pub_date','reviewid']).reset_index(drop=True),pd.concat([failures,duplicates],ignore_index=True)


def sample_by_year_score(frame:pd.DataFrame,start=2020,end=2025,per_cell=35,seed='ARS2026') -> tuple[pd.DataFrame,pd.DataFrame]:
    frame=frame[frame.year.between(start,end)].copy()
    if not len(frame):return frame,frame
    frame['selection_hash']=frame.reviewid.map(lambda rid:hashlib.sha256((seed+'|'+str(rid)).encode()).hexdigest())
    frame=frame.sort_values('selection_hash')
    counts=frame.groupby(['year','score_stratum']).reviewid.transform('size')
    frame['sampling_cell_n']=counts
    frame['sample_n']=counts.clip(upper=per_cell)
    frame['selection_probability']=frame['sample_n']/frame['sampling_cell_n']
    sample=frame.groupby(['year','score_stratum'],group_keys=False).head(per_cell).copy()
    sample=sample.sort_values(['pub_date','reviewid'])
    return frame,sample


def career_pre_review_history(sample:pd.DataFrame,all_reviews:pd.DataFrame,buffer_days=57) -> pd.DataFrame:
    """Measure exposure only using reviews earlier than t-57, never future reviews."""
    s=sample.copy()
    h=all_reviews.copy()
    h['pub_date']=pd.to_datetime(h['pub_date'])
    for i in s.index:
        pub=pd.to_datetime(s.at[i,'pub_date'])
        past=h[(h.artist_norm==s.at[i,'artist_norm']) & (h.pub_date < pub-pd.Timedelta(days=buffer_days))]
        s.at[i,'prior_pitchfork_reviews']=len(past)
        s.at[i,'prior_pitchfork_high_reviews']=int((past.score>=8).sum())
        s.at[i,'prior_pitchfork_bnm']=int(past.bnm.sum()) if 'bnm' in past else 0
        s.at[i,'prior_pitchfork_first_date']=past.pub_date.min().strftime('%Y-%m-%d') if len(past) else ''
        s.at[i,'prior_pitchfork_career_years']=((pub-past.pub_date.min()).days/365.25) if len(past) else 0.0
    for n in ('prior_pitchfork_reviews','prior_pitchfork_high_reviews','prior_pitchfork_bnm'):
        s[n]=s[n].fillna(0).astype('int')
    s['prior_pitchfork_career_years']=s.prior_pitchfork_career_years.fillna(0.)
    return s


def run(source:Path,out:Path,start=2020,end=2025,per_cell=35,seed='ARS2026'):
    out.mkdir(parents=True,exist_ok=True)
    raw=load_catalogue(source)
    frame,excluded=prepare_catalogue(raw)
    all_years,smpl=sample_by_year_score(frame,start,end,per_cell,seed)
    enriched=career_pre_review_history(smpl,frame)
    # Compatible with MusicBrainz resolver and the established event panel pipeline.
    enriched['genre']=enriched.genres_json
    enriched['selection_probability']=enriched.selection_probability.astype('float')
    frame.to_csv(out/'modern_review_census.csv',index=False)
    enriched.to_csv(out/'review_sample.csv',index=False)
    excluded.to_csv(out/'modern_quality_audit.csv',index=False)
    by_year=(all_years.groupby(['year','score_stratum']).size().rename('frame_n').reset_index()
             .merge(smpl.groupby(['year','score_stratum']).size().rename('sample_n').reset_index(),how='outer'))
    by_year['selection_probability']=by_year.sample_n/by_year.frame_n
    by_year.to_csv(out/'modern_sampling_audit.csv',index=False)
    stats={'data_source':str(source),'raw_rows':len(raw),'valid_unique_events':len(frame),
           'eligible_years':int(len(all_years)),'selected_events':int(len(enriched)),
           'year_range':[start,end],'per_year_score_cell':per_cell,'seed':seed,
           'true_wikipedia_complete_n':'not collected yet',
           'sampling_cell_definition':'review publication year x <5, 5-<8, >=8 score'}
    (out/'modern_manifest.json').write_text(json.dumps(stats,indent=2,ensure_ascii=False))
    return stats
