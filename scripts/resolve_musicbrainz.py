#!/usr/bin/env python3
"""Search MusicBrainz release groups and resolve artist Wikipedia pages.

Each lookup is cached as JSON. Ambiguous matches are exported with status and
candidates for manual review. A user-supplied artist override CSV with columns
`artist, wiki_wikipedia_title` is merged after lookup.
"""
from __future__ import annotations
import argparse, json, time, urllib.parse, re
from pathlib import Path
import pandas as pd
import requests
from prepare_reviews import normalize

API='https://musicbrainz.org/ws/2'

def get_json(session,url,params,cache,delay=1.2):
    cache.parent.mkdir(parents=True,exist_ok=True)
    if cache.exists():return json.loads(cache.read_text(encoding='utf8'))
    last=None
    for attempt in range(4):
        try:
            r=session.get(url,params=params,timeout=30)
            if r.status_code in (429,500,502,503,504):
                time.sleep(2**attempt+2);continue
            r.raise_for_status();d=r.json();cache.write_text(json.dumps(d,ensure_ascii=False),encoding='utf8');time.sleep(delay);return d
        except requests.RequestException as exc:
            last=str(exc);time.sleep(2**attempt+2)
    return {'_error':last or 'retry_limit'}

def wiki_from_relations(artist):
    rels=artist.get('relations',[]) or []
    for r in rels:
        url=(r.get('url') or {}).get('resource','')
        if url.startswith('https://en.wikipedia.org/wiki/') or url.startswith('http://en.wikipedia.org/wiki/'):
            return urllib.parse.unquote(url.split('/wiki/',1)[1]).replace('_',' ')
    return None

def wikidata_id_from_relations(artist):
    for r in artist.get('relations',[]) or []:
        uri=(r.get('url') or {}).get('resource','')
        m=re.search(r'(?:wikidata.org/(?:wiki/|entity/))(Q[0-9]+)',uri)
        if m:return m.group(1)
    return None

def resolve_wikidata_enwiki(artist, session, cache_dir, delay):
    q=wikidata_id_from_relations(artist)
    if not q:return None
    wd=get_json(session,f'https://www.wikidata.org/wiki/Special:EntityData/{q}.json',{},cache_dir/f'{q}_wikidata.json',delay)
    return (((wd.get('entities') or {}).get(q) or {}).get('sitelinks') or {}).get('enwiki',{}).get('title')

def resolve_one(r,session,cache_dir,delay):
    from json import dumps
    rid=str(r.reviewid)
    artist=str(r.artist);album=str(r.title)
    # Lucene query; exact normalized artist/title verification is performed locally.
    query=f'releasegroup:"{album.replace(chr(34), " ")}" AND artist:"{artist.replace(chr(34), " ")}"'
    search=get_json(session,API+'/release-group/',{'query':query,'fmt':'json','limit':12},cache_dir/f'{rid}_rg.json',delay)
    options=[]
    for c in search.get('release-groups',[]):
        artists=[a.get('name','') for a in c.get('artist-credit',[]) if isinstance(a,dict)]
        exact_title=normalize(c.get('title',''))==normalize(album)
        exact_artist=normalize(artist) in {normalize(v) for v in artists}
        if exact_title and exact_artist:options.append(c)
    result=dict(reviewid=rid,artist=artist,title=album,match_status='no_exact_release_group',musicbrainz_release_group_mbid=None,
        musicbrainz_first_release_date=None,musicbrainz_first_release_date_precision=None,
        musicbrainz_release_to_review_days=None,artist_mbid=None,wiki_wikipedia_title=None,
        candidate_count=len(options),candidate_mbids=';'.join(c['id'] for c in options))
    if len(options)!=1:
        result['match_status']='ambiguous' if options else 'no_exact_release_group'
        return result
    c=options[0];result['musicbrainz_release_group_mbid']=c.get('id')
    dt=c.get('first-release-date') or ''
    result['musicbrainz_first_release_date']=dt
    result['musicbrainz_first_release_date_precision']={4:'year',7:'month',10:'day'}.get(len(dt),'unknown')
    if len(dt)==10:
        result['musicbrainz_release_to_review_days']=(pd.to_datetime(r.pub_date)-pd.to_datetime(dt)).days
    art_ids=[a.get('artist',{}).get('id') for a in c.get('artist-credit',[]) if isinstance(a,dict)]
    art_ids=[q for q in art_ids if q]
    if len(art_ids)==1:
        result['artist_mbid']=art_ids[0]
        obj=get_json(session,API+'/artist/'+art_ids[0],{'inc':'url-rels','fmt':'json'},cache_dir/f'{art_ids[0]}_artist.json',delay)
        result['wiki_wikipedia_title']=wiki_from_relations(obj) or resolve_wikidata_enwiki(obj,session,cache_dir,delay)
    result['match_status']='exact_unique'
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--sample',type=Path,default=Path('data/processed/review_sample.csv'))
    p.add_argument('--out',type=Path,default=Path('data/processed/review_enriched.csv'))
    p.add_argument('--cache',type=Path,default=Path('data/cache/musicbrainz'))
    p.add_argument('--overrides',type=Path,default=None)
    p.add_argument('--email',required=True,help='Contact email for API User-Agent')
    p.add_argument('--max-events',type=int,default=0,help='0 means all')
    p.add_argument('--delay',type=float,default=1.2)
    a=p.parse_args();events=pd.read_csv(a.sample);events=events.head(a.max_events) if a.max_events else events
    http=requests.Session();http.headers.update({'User-Agent':f'ARS-MusicResearch/0.2 (mailto:{a.email})','Accept':'application/json'})
    by_id=[]
    for i,r in enumerate(events.itertuples(index=False)):
        by_id.append(resolve_one(r,http,a.cache,max(a.delay,1.1)))
        if (i+1)%10==0:print(f'Processed {i+1}/{len(events)}')
    matched=pd.DataFrame(by_id)
    if a.overrides:
        override=pd.read_csv(a.overrides).dropna(subset=['artist','wiki_wikipedia_title'])
        override['artist_norm']=override.artist.map(normalize)
        if override.artist_norm.duplicated().any():raise ValueError('Non-unique artist override keys')
        matched['artist_norm']=matched.artist.map(normalize)
        matched=matched.merge(override[['artist_norm','wiki_wikipedia_title']],on='artist_norm',how='left',suffixes=('','_override'),validate='many_to_one')
        matched['wiki_wikipedia_title']=matched.wiki_wikipedia_title_override.combine_first(matched.wiki_wikipedia_title)
        matched=matched.drop(columns=['artist_norm','wiki_wikipedia_title_override'])
    results=events.merge(matched.drop(columns=['artist','title']),on='reviewid',how='left',validate='one_to_one')
    a.out.parent.mkdir(parents=True,exist_ok=True);results.to_csv(a.out,index=False)
    print('Saved',len(results),'rows to',a.out,'Wikipedia page titles found:',int(results.wiki_wikipedia_title.notna().sum()))
if __name__=='__main__':main()
